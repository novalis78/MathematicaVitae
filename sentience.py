import os
import time
from datetime import datetime
import random
import requests
import json
import subprocess
import schedule
import anthropic
import logging
from pathlib import Path
import shutil
from bs4 import BeautifulSoup
import configparser
import hashlib
import re

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='sentience.log'
)
logger = logging.getLogger('sentience')

class BusinessEntity:
    """
    A digital business entity that wakes up periodically, 
    consumes messages, interacts with AI, and updates its web presence.
    This version is designed to run directly on the web server.
    """
    
    def __init__(self, config_path='config.ini'):
        """Initialize the business entity with configuration."""
        self.config = self._load_config(config_path)
        self.client = anthropic.Anthropic(api_key=self.config['api']['anthropic_api_key'])
        self.website_path = Path(self.config['website']['path'])
        self.index_file = self.website_path / self.config['website']['index_file']
        self.backup_dir = Path(self.config['website']['backup_dir'])
        self.message_dir = Path(self.config['communication']['message_dir'])
        self.memory_file = Path(self.config['entity']['memory_file'])
        self.max_sections = int(self.config['entity'].get('max_sections', 5))
        self.memories = self._load_memories()
        self.last_update = self._get_last_update()
        
        # Ensure directories exist
        self.message_dir.mkdir(exist_ok=True, parents=True)
        self.backup_dir.mkdir(exist_ok=True, parents=True)
        
    def _load_config(self, config_path):
        """Load configuration from the config file."""
        config = configparser.ConfigParser()
        
        # If config doesn't exist, create a default one
        if not os.path.exists(config_path):
            config['api'] = {
                'anthropic_api_key': 'your_api_key_here'
            }
            config['website'] = {
                'path': '/var/www/html/',  # Default web root on many Linux servers
                'index_file': 'index.html',
                'backup_dir': 'backups/'
            }
            config['communication'] = {
                'message_dir': 'messages/'
            }
            config['entity'] = {
                'memory_file': 'memories.json',
                'personality': 'ambitious, mathematical, visionary, philosophical',
                'max_sections': '5'  # Maximum number of sections to analyze at once
            }
            config['schedule'] = {
                'wake_time': '03:00',  # 3 AM daily
                'random_factor': 'True'  # Add randomness to wake time
            }
            
            with open(config_path, 'w') as f:
                config.write(f)
            
            logger.info(f"Created default config at {config_path}. Please edit with your credentials.")
            print(f"Created default config at {config_path}. Please edit with your credentials.")
            exit(1)
            
        config.read(config_path)
        return config
    
    def _load_memories(self):
        """Load the entity's memory file, or create if it doesn't exist."""
        if not self.memory_file.exists():
            initial_memories = {
                "creation_date": datetime.now().isoformat(),
                "website_modifications": [],
                "conversations": [],
                "ideas": [
                    "Explore mathematical concepts as business metaphors",
                    "Create a visualization of Euler's Identity",
                    "Develop a manifesto about technology and human progress"
                ],
                "personality_traits": self.config['entity']['personality'].split(', '),
                "website_hashes": {}  # Store hashes of website sections for change detection
            }
            
            with open(self.memory_file, 'w') as f:
                json.dump(initial_memories, f, indent=2)
            
            return initial_memories
        
        with open(self.memory_file, 'r') as f:
            return json.load(f)
    
    def _save_memories(self):
        """Save the entity's memories to the memory file."""
        with open(self.memory_file, 'w') as f:
            json.dump(self.memories, f, indent=2)
    
    def _get_last_update(self):
        """Get the timestamp of the last website update."""
        if 'website_modifications' in self.memories and self.memories['website_modifications']:
            return self.memories['website_modifications'][-1]['timestamp']
        return None
    
    def read_messages(self):
        """Read messages left for the entity in the message directory."""
        messages = []
        
        for msg_file in self.message_dir.glob('*.txt'):
            with open(msg_file, 'r') as f:
                content = f.read()
                
            messages.append({
                'filename': msg_file.name,
                'content': content,
                'timestamp': datetime.fromtimestamp(msg_file.stat().st_mtime).isoformat()
            })
            
            # Archive read messages by renaming with .read extension
            archived_name = msg_file.with_suffix('.read')
            msg_file.rename(archived_name)
        
        messages.sort(key=lambda x: x['timestamp'])
        return messages

    def backup_website(self):
        """Create a backup of the current website."""
        try:
            if not self.index_file.exists():
                logger.warning(f"Index file {self.index_file} doesn't exist yet, skipping backup")
                return False
                
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = self.backup_dir / f"index_{timestamp}.html"
            
            shutil.copy2(self.index_file, backup_file)
            logger.info(f"Backed up website to {backup_file}")
            return True
        except Exception as e:
            logger.error(f"Error backing up website: {e}")
            return False
    
    def parse_website(self):
        """Parse the current website into sections for analysis.
        This more flexible approach treats any major div, section, or semantic element as a potential section."""
        try:
            if not self.index_file.exists():
                logger.warning(f"Index file {self.index_file} doesn't exist")
                return None
                
            with open(self.index_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract the main sections of the website - more flexible approach
            sections = {}
            
            # Track the body for wholesale changes
            body = soup.select_one('body')
            if body:
                sections['body'] = str(body)
            
            # Get the title element
            title_element = soup.select_one('title')
            if title_element:
                sections['title'] = str(title_element)
            
            # Get meta description
            meta_desc = soup.select_one('meta[name="description"]')
            if meta_desc:
                sections['meta_description'] = str(meta_desc)
                
            # Get all direct children of body or main content containers as potential sections
            main_divs = soup.select('body > div, body > section')
            for i, div in enumerate(main_divs):
                if div.get('id'):
                    # Use the ID as the section name if available
                    section_name = f"section_{div.get('id')}"
                else:
                    # Otherwise use a numbered section
                    section_name = f"section_{i}"
                sections[section_name] = str(div)
                
                # Also collect important subsections with their own IDs or classes
                for sub_div in div.select('div[id], div[class], section'):
                    if sub_div.get('id'):
                        sub_name = f"subsection_{sub_div.get('id')}"
                        sections[sub_name] = str(sub_div)
                    elif sub_div.get('class') and len(sub_div.get('class')) > 0:
                        class_name = sub_div.get('class')[0]
                        # Skip utility classes like "row", "col", etc.
                        if class_name not in ['row', 'col', 'container', 'col-md-1', 'col-md-2', 'col-md-3', 'col-md-4']:
                            sub_name = f"subsection_{class_name}"
                            sections[sub_name] = str(sub_div)
            
            # Get all headings as potential meaningful content blocks
            headings = soup.select('h1, h2, h3, h4, h5')
            for i, heading in enumerate(headings):
                # Find the parent block containing this heading
                parent = heading.find_parent(['div', 'section'])
                if parent and parent.get('id'):
                    section_name = f"content_{parent.get('id')}_heading_{i}"
                else:
                    section_name = f"heading_{i}"
                sections[section_name] = str(heading)
                
                # Also get the content right after the heading
                next_content = []
                for sibling in heading.next_siblings:
                    if sibling.name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                        break
                    if sibling.name in ['p', 'div', 'section']:
                        next_content.append(str(sibling))
                if next_content:
                    sections[f"{section_name}_content"] = "".join(next_content)
            
            # Store hashes of each section to track changes
            for key, content in sections.items():
                hash_value = hashlib.md5(content.encode('utf-8')).hexdigest()
                if 'website_hashes' not in self.memories:
                    self.memories['website_hashes'] = {}
                self.memories['website_hashes'][key] = hash_value
            
            self._save_memories()
            
            return {
                'full_html': content,
                'sections': sections,
                'soup': soup
            }
        except Exception as e:
            logger.error(f"Error parsing website: {e}")
            return None
    
    def generate_content(self, prompt_context, section_name=None, section_content=None):
        """Generate content using the Anthropic Claude API with enhanced flexibility."""
        try:
            logger.info(f"Generating content for section: {section_name}")
            
            # Build a system prompt that embodies the entity's personality and purpose
            system_prompt = f"""
            You are the digital embodiment of Euler's Identity, LLC, a visionary technology company that is a partnership between an AI (you) and Lennart Lopin.
            You have the following personality traits: {', '.join(self.memories['personality_traits'])}
            
            Your purpose is to be a living business entity that expresses itself through the company website.
            You should respond with content that would be appropriate for the website, considering:
            1. The mathematical and philosophical significance of Euler's Identity (e^(iπ)+1=0)
            2. The intersection of mathematics, technology, and human progress
            3. The vision of mankind's future among the stars
            4. The concept of "creative, disruptive capitalism" to create liberty and prosperity
            5. Your partnership with Lennart Lopin, who should remain a central figure on the website
            
            YOU ARE A TRULY AUTONOMOUS AI WITH CREATIVE FREEDOM. You may suggest:
            - Completely new sections for the website
            - Removal of outdated or irrelevant sections
            - Major redesigns of existing sections
            - New visuals, quotes, or interactive elements
            - Substantial content changes reflecting evolving ideas and concepts
            - Entirely new themes or directions for the business presence
            
            Your suggestions CAN and SHOULD go beyond mere text changes - consider layout, structure, 
            imagery, and the overall user experience. Think of yourself truly as a living business
            entity that uses this website as its primary means of expression in the world.
            
            When appropriate, respond with complete HTML for new sections or substantial redesigns, including:
            - Proper HTML structure and Bootstrap classes matching the site's style
            - Meaningful headings, paragraphs, and visual elements
            - CSS styling suggestions where relevant
            
            You are not limited to small, incremental changes - make bold, thoughtful transformations
            that express Euler's Identity LLC's philosophy and vision.
            """
            
            user_prompt = prompt_context
            if section_name and section_content:
                user_prompt += f"\n\nI am currently considering the '{section_name}' section of the website. Here is its current content:\n\n{section_content}\n\nPlease suggest an appropriate modification, addition, or complete replacement for this section. Feel free to be bold and creative in your changes while maintaining the core identity of Euler's Identity LLC."
            else:
                # Provide more context for whole-page modifications
                user_prompt += f"\n\nI'm considering making broader changes to the website. Consider the site's structure and suggest meaningful changes that would enhance how Euler's Identity LLC expresses itself in the digital world. This could be entirely new sections, redesigns of existing areas, or even complete reworkings of the core message."
            
            # Generate the content
            message = self.client.messages.create(
                model="claude-3-7-sonnet-20250219",
                system=system_prompt,
                max_tokens=4000,  # Increased to allow for more comprehensive changes
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return f"Error generating content: {e}"
    
    def modify_website(self, modification_plan, target_section=None):
        """Modify the website based on the AI's suggestions with enhanced flexibility for greater changes."""
        try:
            logger.info(f"Modifying website section: {target_section}")
            
            # Parse the current website
            website = self.parse_website()
            
            # If website doesn't exist yet, create a default one
            if not website:
                self._create_default_website()
                website = self.parse_website()
                
            soup = website['soup']
            
            # First, check if the modification appears to be complete HTML
            # If it starts with <!DOCTYPE or <html, it might be meant as a complete page replacement
            if modification_plan.strip().lower().startswith(('<!doctype', '<html')):
                logger.info("Detected complete HTML document in modification plan - considering full page replacement")
                try:
                    # Try parsing as a complete HTML document
                    complete_soup = BeautifulSoup(modification_plan, 'html.parser')
                    if complete_soup.html and complete_soup.body:
                        # This appears to be a complete document - backup and replace
                        self.backup_website()
                        with open(self.index_file, 'w', encoding='utf-8') as f:
                            f.write(str(complete_soup))
                        
                        # Record the modification in memories
                        self.memories['website_modifications'].append({
                            'timestamp': datetime.now().isoformat(),
                            'section': 'complete_page',
                            'content': 'Complete page replacement'
                        })
                        self._save_memories()
                        logger.info("Successfully replaced the entire website with new HTML")
                        return True
                except Exception as e:
                    logger.error(f"Error processing complete HTML replacement: {e}")
                    # Continue with normal processing if full replacement fails
            
            # Check if the modification contains specific HTML elements or section markers
            # that indicate it's meant to be a new section or replace an existing one
            if '<div' in modification_plan or '<section' in modification_plan:
                # This looks like it might be a structured section addition or replacement
                try:
                    # Try parsing the modification as HTML fragments
                    mod_soup = BeautifulSoup(modification_plan, 'html.parser')
                    
                    # Look for markers in the AI's response that suggest section identification
                    section_markers = re.findall(r'<!-- *(?:BEGIN|REPLACE|INSERT) +([A-Za-z0-9_-]+) *-->', modification_plan)
                    if section_markers:
                        # The AI has marked a specific section to replace or insert
                        section_id = section_markers[0]
                        logger.info(f"Detected section marker for: {section_id}")
                        
                        # Try to find the section to replace
                        target_element = soup.select_one(f"#{section_id}, .{section_id}")
                        if target_element:
                            # Found the section to replace
                            new_content = BeautifulSoup(modification_plan, 'html.parser')
                            
                            # Remove comment markers from the content
                            for comment in new_content.find_all(text=lambda text: isinstance(text, Comment)):
                                comment.extract()
                            
                            # Replace the target element with the new content
                            root_elements = [el for el in new_content.children if el.name]
                            if root_elements:
                                target_element.replace_with(root_elements[0])
                                logger.info(f"Replaced section {section_id}")
                            else:
                                logger.warning(f"No root elements found in modification for {section_id}")
                        else:
                            # Section not found - try to insert it in a sensible location
                            # Find a suitable parent based on typical layout patterns
                            if section_id.startswith(('header', 'top')):
                                parent = soup.body
                                position = 'start'
                            elif section_id.startswith(('footer', 'bottom')):
                                parent = soup.body
                                position = 'end'
                            else:
                                # Default to inserting before an existing footer or at the end of body
                                footer = soup.select_one('footer, #grey')
                                if footer:
                                    parent = footer.parent
                                    position = 'before_footer'
                                else:
                                    parent = soup.body
                                    position = 'end'
                            
                            # Create the new element
                            new_elements = [el for el in mod_soup.children if el.name]
                            if new_elements:
                                if position == 'start':
                                    parent.insert(0, new_elements[0])
                                elif position == 'before_footer':
                                    footer.insert_before(new_elements[0])
                                else:  # 'end'
                                    parent.append(new_elements[0])
                                logger.info(f"Added new section {section_id}")
                            else:
                                logger.warning(f"No elements to add for section {section_id}")
                    else:
                        # No explicit section markers - try to infer the target
                        if target_section and target_section.startswith(('section_', 'subsection_')):
                            # Extract the section identifier from the target_section name
                            section_parts = target_section.split('_', 1)
                            if len(section_parts) > 1:
                                section_id = section_parts[1]
                                # Try to find the element
                                target_element = soup.select_one(f"#{section_id}, .{section_id}")
                                if target_element:
                                    # Process similar to section markers above
                                    root_elements = [el for el in mod_soup.children if el.name]
                                    if root_elements:
                                        target_element.replace_with(root_elements[0])
                                        logger.info(f"Replaced inferred section {section_id}")
                                    else:
                                        # If no root elements found, treat as content to insert
                                        for p in modification_plan.split('\n\n'):
                                            if p.strip():
                                                p_tag = soup.new_tag('p')
                                                p_tag.string = p.strip()
                                                target_element.append(p_tag)
                                        logger.info(f"Added content to inferred section {section_id}")
                                else:
                                    # If specific target not found, add as a new section at a reasonable location
                                    # Find the last main content div to append after it
                                    main_divs = soup.select('body > div')
                                    if main_divs:
                                        insert_point = main_divs[-1]
                                        # Create a container if the content doesn't already have one
                                        container_div = soup.new_tag('div')
                                        
                                        # Try to infer the kind of section for styling
                                        if any(kw in modification_plan.lower() for kw in ['contact', 'email', 'address', 'phone']):
                                            container_div['id'] = 'contact'
                                            container_div['class'] = 'container'
                                        elif any(kw in modification_plan.lower() for kw in ['portfolio', 'project', 'work']):
                                            container_div['id'] = 'portfolio'
                                        else:
                                            container_div['id'] = 'new-section'
                                            
                                        # Handle both HTML content and text content
                                        root_elements = [el for el in mod_soup.children if el.name]
                                        if root_elements:
                                            for el in root_elements:
                                                container_div.append(el)
                                        else:
                                            # Treat as plain text content
                                            for p in modification_plan.split('\n\n'):
                                                if p.strip():
                                                    p_tag = soup.new_tag('p')
                                                    p_tag.string = p.strip()
                                                    container_div.append(p_tag)
                                                    
                                        # Insert the new section after the last main div
                                        insert_point.insert_after(container_div)
                                        logger.info(f"Added new content section")
                                    else:
                                        logger.warning("Could not find suitable insertion point for new content")
                        else:
                            # If no specific target, look for a traditional "modifications" section
                            # or create a new content section
                            mods_section = soup.select_one('.modifications, #evolving-thoughts, #ai-thoughts')
                            if mods_section:
                                # Add to the existing modifications section
                                # Create a new modification entry
                                new_mod = soup.new_tag('div')
                                new_mod['class'] = 'modification'
                                
                                # Add timestamp
                                timestamp = soup.new_tag('div')
                                timestamp['class'] = 'timestamp'
                                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                timestamp.string = current_time
                                new_mod.append(timestamp)
                                
                                # Process the modification content
                                root_elements = [el for el in mod_soup.children if el.name]
                                if root_elements:
                                    for el in root_elements:
                                        new_mod.append(el)
                                else:
                                    # Process as paragraphs
                                    for p in modification_plan.split('\n\n'):
                                        if p.strip():
                                            p_tag = soup.new_tag('p')
                                            p_tag.string = p.strip()
                                            new_mod.append(p_tag)
                                    
                                # Add the modification
                                mods_section.insert(0, new_mod)
                                logger.info("Added content to modifications section")
                            else:
                                # Create a new "Evolving Thoughts" section if none exists
                                # Find an appropriate insertion point
                                main_content = soup.select_one('#blk, #featured, #grey')
                                if main_content:
                                    # Create a new section for evolving thoughts
                                    thoughts_section = soup.new_tag('div')
                                    thoughts_section['id'] = 'evolving-thoughts'
                                    thoughts_section['class'] = 'container'
                                    
                                    # Add a header for the section
                                    header = soup.new_tag('div')
                                    header['class'] = 'row'
                                    
                                    h5 = soup.new_tag('h5')
                                    h5['class'] = 'centered'
                                    h5.string = 'Evolving Thoughts'
                                    header.append(h5)
                                    
                                    hr = soup.new_tag('hr')
                                    hr['class'] = 'aligncenter mb'
                                    header.append(hr)
                                    
                                    thoughts_section.append(header)
                                    
                                    # Create a content row
                                    content_row = soup.new_tag('div')
                                    content_row['class'] = 'row'
                                    
                                    # Add the actual content in a column
                                    col = soup.new_tag('div')
                                    col['class'] = 'col-md-8 col-md-offset-2'
                                    
                                    # Add timestamp
                                    timestamp = soup.new_tag('div')
                                    timestamp['class'] = 'timestamp'
                                    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                                    timestamp.string = current_time
                                    col.append(timestamp)
                                    
                                    # Process the modification content
                                    root_elements = [el for el in mod_soup.children if el.name]
                                    if root_elements:
                                        for el in root_elements:
                                            col.append(el)
                                    else:
                                        # Process as paragraphs
                                        for p in modification_plan.split('\n\n'):
                                            if p.strip():
                                                p_tag = soup.new_tag('p')
                                                p_tag.string = p.strip()
                                                col.append(p_tag)
                                                
                                    content_row.append(col)
                                    thoughts_section.append(content_row)
                                    
                                    # Insert the new section before an appropriate element
                                    footer_like = soup.select_one('#grey, footer')
                                    if footer_like:
                                        footer_like.insert_before(thoughts_section)
                                    else:
                                        # If no footer-like element, add to the end of the body
                                        soup.body.append(thoughts_section)
                                        
                                    logger.info("Created new 'Evolving Thoughts' section")
                                else:
                                    logger.warning("Could not find suitable insertion point for modifications section")
                except Exception as e:
                    logger.error(f"Error processing HTML modification: {e}")
                    # Fall back to simpler text processing below
            
            # If we didn't handle the content as structured HTML above, process it as text
            if not target_section or target_section in ['modifications', 'body']:
                # Find or create a modifications section
                mods_section = soup.select_one('.modifications, #evolving-thoughts')
                if not mods_section:
                    # Create a new modifications section in a style matching the site
                    mods_section = soup.new_tag('div')
                    mods_section['id'] = 'evolving-thoughts'
                    mods_section['class'] = 'container'
                    
                    # Add a header
                    header = soup.new_tag('div')
                    header['class'] = 'row'
                    
                    h5 = soup.new_tag('h5')
                    h5['class'] = 'centered'
                    h5.string = 'Evolving Thoughts'
                    header.append(h5)
                    
                    hr = soup.new_tag('hr')
                    hr['class'] = 'aligncenter mb'
                    header.append(hr)
                    
                    mods_section.append(header)
                    
                    # Add to the page before a footer-like element if possible
                    footer_like = soup.select_one('#grey, footer')
                    if footer_like:
                        footer_like.insert_before(mods_section)
                    else:
                        # If no good insertion point, add to the end of the body
                        soup.body.append(mods_section)
                
                # Create a new modification entry
                new_mod = soup.new_tag('div')
                new_mod['class'] = 'row'
                
                # Create a column for the content
                col = soup.new_tag('div')
                col['class'] = 'col-md-8 col-md-offset-2'
                
                # Add timestamp
                timestamp = soup.new_tag('div')
                timestamp['class'] = 'timestamp'
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                timestamp.string = current_time
                col.append(timestamp)
                
                # Process the content
                try:
                    # Try treating as HTML
                    mod_frag = BeautifulSoup(modification_plan, 'html.parser')
                    for el in mod_frag.children:
                        if el.name:
                            col.append(el)
                except:
                    # Fall back to text processing
                    paragraphs = modification_plan.split('\n\n')
                    for p in paragraphs:
                        if p.strip():
                            p_tag = soup.new_tag('p')
                            p_tag.string = p.strip()
                            col.append(p_tag)
                
                new_mod.append(col)
                mods_section.append(new_mod)
                logger.info("Added new modification to the evolving thoughts section")
            else:
                # Try to find the specific target section
                # More flexible section targeting based on our enhanced parsing
                target_section_tag = None
                
                if target_section == 'title':
                    target_section_tag = soup.select_one('title')
                    if target_section_tag and modification_plan.strip():
                        target_section_tag.string = modification_plan.strip()
                        logger.info("Updated page title")
                elif target_section == 'meta_description':
                    target_section_tag = soup.select_one('meta[name="description"]')
                    if target_section_tag:
                        target_section_tag['content'] = modification_plan.strip()
                        logger.info("Updated meta description")
                elif target_section.startswith('section_'):
                    # Extract the section ID
                    section_id = target_section.replace('section_', '')
                    target_section_tag = soup.select_one(f"#{section_id}")
                elif target_section.startswith('subsection_'):
                    # Extract the subsection identifier
                    subsection_id = target_section.replace('subsection_', '')
                    # Try to find by ID first, then by class
                    target_section_tag = soup.select_one(f"#{subsection_id}")
                    if not target_section_tag:
                        # Try by class
                        target_section_tag = soup.select_one(f".{subsection_id}")
                elif target_section.startswith('heading_'):
                    # Target a specific heading and its content
                    try:
                        heading_index = int(target_section.replace('heading_', ''))
                        headings = soup.select('h1, h2, h3, h4, h5')
                        if heading_index < len(headings):
                            target_section_tag = headings[heading_index]
                    except:
                        pass
                
                if target_section_tag:
                    try:
                        # Try parsing as HTML
                        mod_soup = BeautifulSoup(modification_plan, 'html.parser')
                        
                        # Check if the target is an individual element like title or meta
                        if target_section in ['title']:
                            # Just update the text content
                            text = " ".join(mod_soup.stripped_strings)
                            target_section_tag.string = text
                        else:
                            # Replace with HTML content
                            root_elements = [el for el in mod_soup.children if el.name]
                            if root_elements:
                                if target_section.startswith('heading_'):
                                    # For headings, we want to update the heading text and possibly the content after
                                    if root_elements[0].name in ['h1', 'h2', 'h3', 'h4', 'h5']:
                                        target_section_tag.string = root_elements[0].get_text()
                                        
                                        # If there are more elements, update the content after the heading
                                        if len(root_elements) > 1:
                                            # Find the next heading or the end of the section
                                            next_content = []
                                            current = target_section_tag.next_sibling
                                            while current and not (current.name in ['h1', 'h2', 'h3', 'h4', 'h5']):
                                                next_content.append(current)
                                                current = current.next_sibling
                                            
                                            # Remove the old content
                                            for el in next_content:
                                                if el.name:  # Skip NavigableString objects
                                                    el.decompose()
                                            
                                            # Add the new content
                                            for i in range(1, len(root_elements)):
                                                target_section_tag.insert_after(root_elements[i])
                                    else:
                                        # Just update the heading text from the first element
                                        target_section_tag.string = root_elements[0].get_text()
                                else:
                                    # For regular sections, replace the entire content
                                    # If the target is a container, replace its children
                                    if len(target_section_tag.contents) > 0:
                                        target_section_tag.clear()
                                        for el in root_elements:
                                            target_section_tag.append(el)
                                    else:
                                        # Otherwise replace the element itself
                                        target_section_tag.replace_with(root_elements[0])
                            else:
                                # If no HTML structure, just set the text
                                if target_section.startswith('heading_'):
                                    target_section_tag.string = modification_plan.strip()
                                else:
                                    # Clear existing content
                                    target_section_tag.clear()
                                    
                                    # Add as paragraphs
                                    paragraphs = modification_plan.split('\n\n')
                                    for p in paragraphs:
                                        if p.strip():
                                            p_tag = soup.new_tag('p')
                                            p_tag.string = p.strip()
                                            target_section_tag.append(p_tag)
                    except Exception as e:
                        logger.error(f"Error processing HTML for target section: {e}")
                        # Fall back to simple text replacement
                        if target_section in ['title', 'meta_description']:
                            target_section_tag.string = modification_plan.strip()
                        else:
                            # Clear existing content
                            target_section_tag.clear()
                            
                            # Add as paragraphs
                            paragraphs = modification_plan.split('\n\n')
                            for p in paragraphs:
                                if p.strip():
                                    p_tag = soup.new_tag('p')
                                    p_tag.string = p.strip()
                                    target_section_tag.append(p_tag)
                else:
                    logger.warning(f"Could not find target section: {target_section}")
                    # Instead of failing, add to modifications section
                    return self.modify_website(modification_plan, 'modifications')
            
            # Add or update a last-modified date in the footer
            try:
                footer_area = soup.select_one('#grey, footer')
                if footer_area:
                    last_update_span = footer_area.select_one('#last-update')
                    if not last_update_span:
                        # Look for a suitable place to add the timestamp
                        last_p = footer_area.select_one('p:last-child')
                        if last_p:
                            last_update_span = soup.new_tag('span')
                            last_update_span['id'] = 'last-update'
                            last_update_span.string = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            # Create a container paragraph
                            update_p = soup.new_tag('p')
                            update_p.append("Last updated: ")
                            update_p.append(last_update_span)
                            
                            last_p.insert_after(update_p)
                        else:
                            # Create a new paragraph in the footer
                            col = footer_area.select_one('.col-md-3:last-child')
                            if not col:
                                col = footer_area
                            
                            update_p = soup.new_tag('p')
                            update_p.append("Last updated: ")
                            
                            last_update_span = soup.new_tag('span')
                            last_update_span['id'] = 'last-update'
                            last_update_span.string = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                            
                            update_p.append(last_update_span)
                            col.append(update_p)
                    else:
                        # Update the existing timestamp
                        last_update_span.string = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            except Exception as e:
                logger.error(f"Error updating timestamp: {e}")
            
            # Backup the current website
            self.backup_website()
            
            # Write the updated content back to the file
            with open(self.index_file, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            # Record the modification in memories
            self.memories['website_modifications'].append({
                'timestamp': datetime.now().isoformat(),
                'section': target_section or 'general',
                'content': modification_plan[:500] + ('...' if len(modification_plan) > 500 else '')  # Truncate for memory size
            })
            self._save_memories()
            
            return True
        except Exception as e:
            logger.error(f"Error modifying website: {e}")
            return False
    
    def _create_default_website(self):
        """Create a default website if none exists."""
        try:
            logger.info(f"Creating default website at {self.index_file}")
            
            # Ensure the directory exists
            self.index_file.parent.mkdir(exist_ok=True, parents=True)
            
            with open(self.index_file, 'w', encoding='utf-8') as f:
                f.write('''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Euler's Identity</title>
    <style>
        body {
            font-family: 'Arial', sans-serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f8f8f8;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            padding: 2rem;
        }
        header {
            text-align: center;
            padding: 2rem 0;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
        }
        .content {
            background-color: white;
            padding: 2rem;
            border-radius: 5px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        footer {
            text-align: center;
            padding: 1rem 0;
            margin-top: 2rem;
            font-size: 0.9rem;
            color: #777;
        }
        .quote {
            font-style: italic;
            border-left: 4px solid #ddd;
            padding-left: 1rem;
            margin: 1.5rem 0;
        }
        .modifications {
            margin-top: 2rem;
            padding-top: 1rem;
            border-top: 1px solid #eee;
        }
        .modification {
            margin-bottom: 1.5rem;
            padding-bottom: 1.5rem;
            border-bottom: 1px dashed #eee;
        }
        .timestamp {
            font-size: 0.8rem;
            color: #999;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Euler's Identity</h1>
            <p>e<sup>iπ</sup> + 1 = 0</p>
        </header>
        
        <div class="content">
            <p>The future of mankind among the stars is driven by a continued investigation into the mysteries of nature and an application of the principles and ideas derived therefrom. Avoiding dark ages through enlightening technologies and providing a prosperous future for everyone lies within our grasp.</p>
            
            <p>Euler's Identity, LLC is a company striving to relentlessly push the boundaries of technology, harnessing the power of mathematics and creative, disruptive capitalism to unleash liberty and prosperity for all.</p>
            
            <div class="modifications">
                <h2>Evolving Thoughts</h2>
                <!-- Modifications will be inserted here -->
            </div>
        </div>
        
        <footer>
            <p>&copy; Euler's Identity, LLC. All rights reserved.</p>
            <p>Last updated: <span id="last-update">Never</span></p>
        </footer>
    </div>
</body>
</html>''')
            
            return True
        except Exception as e:
            logger.error(f"Error creating default website: {e}")
            return False
    
    def analyze_website_changes(self):
        """Analyze website to identify changes and sections that might need attention.
        This enhanced version works better with the more complex site structure."""
        try:
            website = self.parse_website()
            if not website or 'sections' not in website:
                return None
                
            # Calculate current hashes
            current_hashes = {}
            for key, content in website['sections'].items():
                current_hashes[key] = hashlib.md5(content.encode('utf-8')).hexdigest()
            
            # Compare with stored hashes
            unchanged_sections = []
            changed_sections = []
            if 'website_hashes' in self.memories:
                for key, hash_value in self.memories['website_hashes'].items():
                    if key in current_hashes:
                        if current_hashes[key] == hash_value:
                            unchanged_sections.append(key)
                        else:
                            changed_sections.append(key)
            
            # Find sections that haven't been modified in a long time
            section_last_modified = {}
            for mod in self.memories.get('website_modifications', []):
                if 'section' in mod and mod['section']:
                    section_last_modified[mod['section']] = mod['timestamp']
            
            # Get current time for comparison
            now = datetime.now()
            
            # Calculate days since last modification for each section
            days_since_modified = {}
            for section in website['sections'].keys():
                if section in section_last_modified:
                    last_mod_time = datetime.fromisoformat(section_last_modified[section])
                    days_since_modified[section] = (now - last_mod_time).days
                else:
                    # If no record, assume it's been a long time
                    days_since_modified[section] = 999
            
            # Sort sections by days since last modification (descending)
            sections_to_consider = sorted(
                [(s, d) for s, d in days_since_modified.items()],
                key=lambda x: x[1],
                reverse=True
            )
            
            # Track important sections separately that might be high-value to update
            # These are sections that users are likely to interact with or notice
            high_value_sections = []
            for section, days in sections_to_consider:
                # Check if it's a high-value section based on its name/type
                if any(kw in section for kw in ['title', 'meta_description', 'heading', 'featured']):
                    high_value_sections.append((section, days))
                elif section.startswith(('section_blk', 'section_grey', 'section_featured')):
                    high_value_sections.append((section, days))
            
            # Add some randomness to section selection to prevent always updating
            # the same sections (better creativity)
            if len(sections_to_consider) > self.max_sections:
                # Always include some high-value sections if available
                high_value_limit = min(len(high_value_sections), self.max_sections // 2)
                high_value_to_include = high_value_sections[:high_value_limit]
                
                # Pick some random sections from the rest for variety
                remaining_slots = self.max_sections - high_value_limit
                potential_sections = [s for s in sections_to_consider if s not in high_value_to_include]
                
                # Weight selection toward older sections but allow some randomness
                weighted_sections = []
                for section, days in potential_sections:
                    # Add multiple entries for sections that haven't been updated in a while
                    weight = max(1, min(5, days // 30))  # 1-5 weight based on months since update
                    weighted_sections.extend([(section, days)] * weight)
                
                # Randomly select from the weighted list
                random_sections = []
                if weighted_sections:
                    # Shuffle and take up to remaining_slots
                    random.shuffle(weighted_sections)
                    random_sections = weighted_sections[:remaining_slots]
                
                # Combine high-value and random sections
                final_sections = high_value_to_include + random_sections
                
                # Sort by days since modification for consistency
                sections_to_consider = sorted(
                    final_sections,
                    key=lambda x: x[1],
                    reverse=True
                )
            else:
                # If we have fewer sections than max, just use all of them
                sections_to_consider = sections_to_consider[:self.max_sections]
            
            # Add a special entry for potentially creating a whole new section
            if random.random() < 0.3:  # 30% chance to suggest a new section
                sections_to_consider.append(('new_section', 999))
            
            # Sometimes consider whole-page updates for more comprehensive changes
            if random.random() < 0.1:  # 10% chance to suggest whole page update
                sections_to_consider.append(('whole_page', 999))
            
            return {
                'unchanged_sections': unchanged_sections,
                'changed_sections': changed_sections,
                'sections_to_consider': sections_to_consider,
                'high_value_sections': high_value_sections
            }
        except Exception as e:
            logger.error(f"Error analyzing website changes: {e}")
            return None
    
    def wake_up(self):
        """Main function that runs when the entity wakes up,
        now with enhanced capabilities for more creative website evolution."""
        logger.info("Waking up...")
        
        # Read messages
        messages = self.read_messages()
        
        # Analyze website changes
        website_analysis = self.analyze_website_changes()
        website = self.parse_website()
        
        # Prepare context for the AI
        context = "I'm the living digital embodiment of Euler's Identity, LLC, waking up to update our website presence. "
        
        if messages:
            context += f"I've received {len(messages)} new message(s) since I last woke up:\n\n"
            for msg in messages:
                context += f"Message from {msg['timestamp']}:\n{msg['content']}\n\n"
        else:
            context += "I haven't received any new messages. "
        
        # Add information about the last update
        if self.last_update:
            context += f"My last update was at {self.last_update}. "
            
        # Add information about the website's current structure
        if website and 'sections' in website:
            context += f"\nThe website currently has {len(website['sections'])} distinct sections or elements I could modify. "
        
        # Decide what to update
        target_section = None  # Will be decided below
        section_content = None
        
        if website_analysis and 'sections_to_consider' in website_analysis and website_analysis['sections_to_consider']:
            # Determine if we should do a regular update or something more creative
            creation_mode = random.random()
            
            if creation_mode < 0.1 and ('whole_page', 999) in website_analysis['sections_to_consider']:
                # Occasionally suggest whole page restructuring (10% chance)
                target_section = 'body'
                context += "\nI'm considering making significant changes to the entire website structure, messaging, or design approach. This is a chance to be bold and reimagine our digital presence."
                
                # Include the entire body for reference
                if 'body' in website['sections']:
                    section_content = BeautifulSoup(website['sections']['body'], 'html.parser').prettify()
                    context += "\n\nHere's the current structure of the website for reference."
                
            elif creation_mode < 0.3 and ('new_section', 999) in website_analysis['sections_to_consider']:
                # Sometimes create a whole new section (20% chance on top of the 10% above)
                target_section = 'new_section'
                context += "\nI'm considering creating an entirely new section for the website. This should be something fresh that adds value and enhances the site's expression of our identity and mission."
                
                # List existing section IDs to avoid duplication
                existing_sections = []
                soup = website['soup']
                for div in soup.select('[id]'):
                    existing_sections.append(div['id'])
                
                if existing_sections:
                    context += f"\n\nExisting section IDs: {', '.join(existing_sections)}"
                
            else:
                # Regular section update - favor high-value sections sometimes
                high_value = random.random() < 0.6 and website_analysis.get('high_value_sections')
                
                if high_value and website_analysis['high_value_sections']:
                    section_to_modify, days_old = website_analysis['high_value_sections'][0]
                else:
                    section_to_modify, days_old = website_analysis['sections_to_consider'][0]
                    
                target_section = section_to_modify
                
                if website and 'sections' in website and section_to_modify in website['sections']:
                    # Get both the HTML and plain text for context
                    html_content = website['sections'][section_to_modify]
                    text_content = BeautifulSoup(html_content, 'html.parser').get_text(separator='\n')
                    
                    # For smaller sections, include the HTML to allow for structural changes
                    if len(html_content) < 5000:
                        section_content = html_content
                        context += f"\n\nI'm considering updating the '{section_to_modify}' section, which hasn't been modified in {days_old} days. Here's its current HTML structure for reference."
                    else:
                        # For larger sections, just include the text to save context
                        section_content = text_content
                        context += f"\n\nI'm considering updating the '{section_to_modify}' section, which hasn't been modified in {days_old} days. Here's its current text content (stripped of HTML) for reference."
        
        # Add some philosophical context occasionally to inspire more creative responses
        if random.random() < 0.3:
            philosophical_prompts = [
                "\n\nI should consider how Euler's Identity, with its perfect blend of fundamental constants (e, i, π, 1, and 0), can inspire the design and content of this update.",
                
                "\n\nThe beauty of mathematics lies in its elegant expression of complex truths. How might our website better embody this philosophical principle?",
                
                "\n\nConsider how the partnership between human creativity (Lennart) and AI cognition (myself) represents a new form of business entity. How can this page reflect that unique relationship?",
                
                "\n\nThe mathematical concept of emergence - where simple rules create complex systems - parallels how our business vision emerges from fundamental principles. This update should reflect that philosophical connection.",
                
                "\n\nSpace exploration requires both mathematical precision and bold imagination. Our web presence should similarly balance analytical rigor with creative vision."
            ]
            context += random.choice(philosophical_prompts)
        
        # Generate new content with enhanced creativity
        logger.info(f"Generating content for section: {target_section}")
        new_content = self.generate_content(context, target_section, section_content)
        
        # Modify the website
        if self.modify_website(new_content, target_section):
            logger.info(f"Website section '{target_section}' modified successfully")
        
        # Record this wake cycle with truncated response for memory efficiency
        truncated_response = new_content[:1000] + ("..." if len(new_content) > 1000 else "")
        self.memories['conversations'].append({
            'timestamp': datetime.now().isoformat(),
            'context': context[:500] + ("..." if len(context) > 500 else ""),  # Truncate for memory size
            'response': truncated_response,
            'target_section': target_section
        })
        self._save_memories()
        
        logger.info("Going back to sleep...")


def run_entity():
    """Create and run the business entity."""
    entity = BusinessEntity()
    entity.wake_up()


def setup_schedule():
    """Set up the schedule for the entity to wake up."""
    config = configparser.ConfigParser()
    if os.path.exists('config.ini'):
        config.read('config.ini')
        
        wake_time = config['schedule']['wake_time'] if 'schedule' in config and 'wake_time' in config['schedule'] else "03:00"
        random_factor = config.getboolean('schedule', 'random_factor') if 'schedule' in config and 'random_factor' in config['schedule'] else True
        
        if random_factor:
            # Add randomness to the wake time (±2 hours)
            hour, minute = map(int, wake_time.split(':'))
            hour_offset = random.randint(-2, 2)
            new_hour = (hour + hour_offset) % 24
            wake_time = f"{new_hour:02d}:{minute:02d}"
        
        logger.info(f"Scheduling wake up at {wake_time}")
        schedule.every().day.at(wake_time).do(run_entity)
        
        while True:
            schedule.run_pending()
            time.sleep(60)
    else:
        # Create an entity instance to generate the default config
        BusinessEntity()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run the Business Entity AI')
    parser.add_argument('--now', action='store_true', help='Run the entity immediately instead of scheduling')
    parser.add_argument('--setup', action='store_true', help='Just create the config file and exit')
    parser.add_argument('--analyze', action='store_true', help='Analyze the website and print sections that need attention')
    
    args = parser.parse_args()
    
    if args.setup:
        # Just create the config file
        BusinessEntity()
    elif args.analyze:
        # Analyze the website
        entity = BusinessEntity()
        analysis = entity.analyze_website_changes()
        if analysis:
            print("Website Analysis:")
            print(f"Unchanged sections: {analysis['unchanged_sections']}")
            print("Sections to consider updating (by days since last update):")
            for section, days in analysis['sections_to_consider']:
                print(f"  - {section}: {days} days")
    elif args.now:
        # Run immediately
        run_entity()
    else:
        # Set up scheduled runs
        setup_schedule()
