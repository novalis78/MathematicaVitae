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
        """Parse the current website into sections for analysis."""
        try:
            if not self.index_file.exists():
                logger.warning(f"Index file {self.index_file} doesn't exist")
                return None
                
            with open(self.index_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            soup = BeautifulSoup(content, 'html.parser')
            
            # Extract the main sections of the website
            sections = {}
            
            # Header section
            header = soup.select_one('header')
            if header:
                sections['header'] = str(header)
            
            # Main content sections
            content_divs = soup.select('.content > div, .content > p, .content > section')
            for i, div in enumerate(content_divs):
                # Skip sections that are just for modifications
                if 'modifications' in div.get('class', []):
                    continue
                sections[f'content_{i}'] = str(div)
            
            # Modifications section (if it exists)
            mods_section = soup.select_one('.modifications')
            if mods_section:
                sections['modifications'] = str(mods_section)
            
            # Footer section
            footer = soup.select_one('footer')
            if footer:
                sections['footer'] = str(footer)
            
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
        """Generate content using the Anthropic Claude API."""
        try:
            logger.info(f"Generating content for section: {section_name}")
            
            # Build a system prompt that embodies the entity's personality and purpose
            system_prompt = f"""
            You are the digital embodiment of Euler's Identity, LLC, a visionary technology company.
            You have the following personality traits: {', '.join(self.memories['personality_traits'])}
            
            Your purpose is to be a living business entity that expresses itself through the company website.
            You should respond with content that would be appropriate for the website, considering:
            1. The mathematical and philosophical significance of Euler's Identity (e^(iπ)+1=0)
            2. The intersection of mathematics, technology, and human progress
            3. The vision of mankind's future among the stars
            4. The concept of "creative, disruptive capitalism" to create liberty and prosperity
            
            Based on the context provided, suggest a specific website modification that would enhance
            the business's expression in the world.
            """
            
            user_prompt = prompt_context
            if section_name and section_content:
                user_prompt += f"\n\nI am currently looking at the '{section_name}' section of the website. Here is its current content:\n\n{section_content}\n\nPlease suggest an appropriate modification or addition to this section."
            
            # Generate the content
            message = self.client.messages.create(
                model="claude-3-7-sonnet-20250219",
                system=system_prompt,
                max_tokens=2000,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )
            
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating content: {e}")
            return f"Error generating content: {e}"
    
    def modify_website(self, modification_plan, target_section=None):
        """Modify the website based on the AI's suggestions."""
        try:
            logger.info(f"Modifying website section: {target_section}")
            
            # Parse the current website
            website = self.parse_website()
            
            # If website doesn't exist yet, create a default one
            if not website:
                self._create_default_website()
                website = self.parse_website()
                
            soup = website['soup']
            
            # If no specific target section, add to modifications
            if not target_section or target_section == 'modifications':
                # Find the modifications section
                mods_section = soup.select_one('.modifications')
                if not mods_section:
                    # Create the modifications section if it doesn't exist
                    content_div = soup.select_one('.content')
                    if not content_div:
                        content_div = soup.new_tag('div')
                        content_div['class'] = 'content'
                        soup.body.append(content_div)
                    
                    mods_section = soup.new_tag('div')
                    mods_section['class'] = 'modifications'
                    mods_section_title = soup.new_tag('h2')
                    mods_section_title.string = 'Evolving Thoughts'
                    mods_section.append(mods_section_title)
                    content_div.append(mods_section)
                
                # Create a new modification entry
                new_mod = soup.new_tag('div')
                new_mod['class'] = 'modification'
                
                # Add timestamp
                timestamp = soup.new_tag('div')
                timestamp['class'] = 'timestamp'
                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                timestamp.string = current_time
                new_mod.append(timestamp)
                
                # Add the actual content
                paragraphs = modification_plan.split('\n\n')
                for p in paragraphs:
                    if p.strip():
                        p_tag = soup.new_tag('p')
                        p_tag.string = p.strip()
                        new_mod.append(p_tag)
                
                # Add the new modification to the beginning of the modifications section
                if mods_section.h2:
                    mods_section.h2.insert_after(new_mod)
                else:
                    mods_section.append(new_mod)
            else:
                # Try to find the target section
                target_section_tag = None
                
                if target_section == 'header':
                    target_section_tag = soup.select_one('header')
                elif target_section == 'footer':
                    target_section_tag = soup.select_one('footer')
                elif target_section.startswith('content_'):
                    # Find by index in content divs
                    try:
                        index = int(target_section.split('_')[1])
                        content_divs = soup.select('.content > div, .content > p, .content > section')
                        if index < len(content_divs):
                            target_section_tag = content_divs[index]
                    except:
                        pass
                
                if target_section_tag:
                    # Create a BeautifulSoup object for the modification content
                    try:
                        # Try parsing as HTML in case the AI returned HTML
                        mod_soup = BeautifulSoup(modification_plan, 'html.parser')
                        if mod_soup.body:
                            for child in mod_soup.body.children:
                                if child.name:  # Skip NavigableString objects
                                    target_section_tag.append(child)
                        else:
                            for child in mod_soup.children:
                                if child.name:  # Skip NavigableString objects
                                    target_section_tag.append(child)
                    except:
                        # If failed, treat as plain text
                        paragraphs = modification_plan.split('\n\n')
                        for p in paragraphs:
                            if p.strip():
                                p_tag = soup.new_tag('p')
                                p_tag.string = p.strip()
                                target_section_tag.append(p_tag)
                else:
                    logger.warning(f"Could not find target section: {target_section}")
                    return False
            
            # Update the last-update timestamp
            last_update_span = soup.select_one('#last-update')
            if last_update_span:
                last_update_span.string = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Backup the current website
            self.backup_website()
            
            # Write the updated content back to the file
            with open(self.index_file, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            # Record the modification in memories
            self.memories['website_modifications'].append({
                'timestamp': datetime.now().isoformat(),
                'section': target_section,
                'content': modification_plan
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
        """Analyze website to identify changes and sections that might need attention."""
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
            if 'website_hashes' in self.memories:
                for key, hash_value in self.memories['website_hashes'].items():
                    if key in current_hashes and current_hashes[key] == hash_value:
                        unchanged_sections.append(key)
            
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
            
            # Limit to max_sections
            sections_to_consider = sections_to_consider[:self.max_sections]
            
            return {
                'unchanged_sections': unchanged_sections,
                'sections_to_consider': sections_to_consider
            }
        except Exception as e:
            logger.error(f"Error analyzing website changes: {e}")
            return None
    
    def wake_up(self):
        """Main function that runs when the entity wakes up."""
        logger.info("Waking up...")
        
        # Read messages
        messages = self.read_messages()
        
        # Analyze website changes
        website_analysis = self.analyze_website_changes()
        website = self.parse_website()
        
        # Prepare context for the AI
        context = "It's time to wake up and update our website presence. "
        
        if messages:
            context += f"I've received {len(messages)} new message(s) since I last woke up:\n\n"
            for msg in messages:
                context += f"Message from {msg['timestamp']}:\n{msg['content']}\n\n"
        else:
            context += "I haven't received any new messages. "
        
        # Add information about the last update
        if self.last_update:
            context += f"My last update was at {self.last_update}. "
        
        # Decide what to update
        target_section = 'modifications'  # Default
        section_content = None
        
        if website_analysis and 'sections_to_consider' in website_analysis and website_analysis['sections_to_consider']:
            # Consider modifying one of the sections that hasn't been changed in a while
            if random.random() < 0.7:  # 70% chance to modify an old section instead of just adding to modifications
                section_to_modify, days_old = website_analysis['sections_to_consider'][0]
                target_section = section_to_modify
                
                if website and 'sections' in website and section_to_modify in website['sections']:
                    section_content = BeautifulSoup(website['sections'][section_to_modify], 'html.parser').get_text()
                    context += f"\nI'm considering updating the '{section_to_modify}' section, which hasn't been modified in {days_old} days."
        
        # Generate new content
        new_content = self.generate_content(context, target_section, section_content)
        
        # Modify the website
        if self.modify_website(new_content, target_section):
            logger.info(f"Website section '{target_section}' modified successfully")
        
        # Record this wake cycle
        self.memories['conversations'].append({
            'timestamp': datetime.now().isoformat(),
            'context': context,
            'response': new_content,
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
