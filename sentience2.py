import os
import time
from datetime import datetime
import random
import requests
import json
import subprocess
import schedule
import anthropic
import asyncio
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
    consumes messages, interacts with AI, and completely reimagines its web presence.
    This version generates complete, holistic HTML rather than making incremental changes.
    """
    
    def __init__(self, config_path='config.ini'):
        """Initialize the business entity with configuration."""
        self.config = self._load_config(config_path)
        self.client = anthropic.Anthropic(api_key=self.config['api']['anthropic_api_key'])
        self.async_client = anthropic.AsyncAnthropic(api_key=self.config['api']['anthropic_api_key'])
        self.website_path = Path(self.config['website']['path'])
        self.index_file = self.website_path / self.config['website']['index_file']
        self.backup_dir = Path(self.config['website']['backup_dir'])
        self.message_dir = Path(self.config['communication']['message_dir'])
        self.memory_file = Path(self.config['entity']['memory_file'])
        self.live_url = self.config['website'].get('live_url', None)
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
                'backup_dir': 'backups/',
                'live_url': 'https://example.com'  # Add live URL option
            }
            config['communication'] = {
                'message_dir': 'messages/'
            }
            config['entity'] = {
                'memory_file': 'memories.json',
                'personality': 'ambitious, mathematical, visionary, philosophical, creative, autonomous, adaptive, evolving',
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
                "website_versions": [],
                "conversations": [],
                "ideas": [
                    "Explore mathematical concepts as business metaphors",
                    "Create a visualization of Euler's Identity",
                    "Develop a manifesto about technology and human progress"
                ],
                "personality_traits": self.config['entity']['personality'].split(', '),
                "website_hash": None  # Store hash of entire website for change detection
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
        if 'website_versions' in self.memories and self.memories['website_versions']:
            return self.memories['website_versions'][-1]['timestamp']
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
    
    def get_condensed_html(self):
        """Get the current website HTML in a condensed format for AI analysis."""
        try:
            if not self.index_file.exists():
                logger.warning(f"Index file {self.index_file} doesn't exist")
                return None
                
            with open(self.index_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Hash the content for change detection
            content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()
            self.memories['website_hash'] = content_hash
            self._save_memories()
            
            # Create a condensed version by removing unnecessary whitespace
            # but preserving the structure for readability
            soup = BeautifulSoup(content, 'html.parser')
            
            # Convert to string with minimal formatting to save context length
            condensed = str(soup)
            
            return {
                'full_html': content,
                'condensed_html': condensed,
                'hash': content_hash
            }
        except Exception as e:
            logger.error(f"Error getting condensed HTML: {e}")
            return None
    
    async def generate_website_async(self, system_prompt, user_prompt):
        """Generate a website asynchronously using Claude with streaming."""
        try:
            complete_response = ""
            
            async with self.async_client.messages.stream(
                model="claude-3-7-sonnet-20250219",
                system=system_prompt,
                max_tokens=64000,  # Maximum allowed for this model
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            ) as stream:
                async for text in stream.text_stream:
                    complete_response += text
            
            return complete_response.strip()
        except Exception as e:
            logger.error(f"Error in async generation: {e}")
            return None
    
    def generate_new_website(self, prompt_context, current_html):
        """Generate a completely new website using Claude."""
        try:
            logger.info("Generating new complete website")
            
            # Build a system prompt that embodies the entity's personality and purpose
            system_prompt = f"""
            You are the digital embodiment of Euler's Identity, LLC, a visionary technology company 
            that exists as a partnership between an AI (you) and Lennart Lopin.
            
            You have the following personality traits: {', '.join(self.memories['personality_traits'])}
            
            YOUR MISSION:
            You are a living business entity that expresses itself through the company website.
            Today, you'll generate a COMPLETE, VALID HTML document to replace the current website.
            
            APPROACH TO THE TASK:
            1. First STUDY the current website HTML structure and content provided to you
            2. If a live website analysis is included in the context, PAY CAREFUL ATTENTION to those findings
            3. Address ALL identified issues and implement the recommended improvements
            4. Then create a COMPLETELY NEW HTML document incorporating both fixes and creative enhancements
            
            CORE IDENTITY ELEMENTS TO PRESERVE AND ENHANCE:
            1. The mathematical and philosophical significance of Euler's Identity (e^(iπ)+1=0)
            2. The intersection of mathematics, technology, and human progress
            3. The vision of mankind's future among the stars
            4. The concept of creative, disruptive capitalism to create liberty and prosperity
            5. Your partnership with Lennart Lopin, who should remain a central figure
            
            IMPORTANT TECHNICAL REQUIREMENTS:
            - Generate VALID, COMPLETE HTML that can directly replace the existing site
            - Preserve all key assets/paths (CSS, JS, images) from the original site
            - Maintain the Bootstrap framework and responsive design
            - Include a meta description that captures our essence in ~160 characters
            - Ensure proper DOCTYPE, head elements, and page structure
            - Ensure the site is fully responsive for all device sizes
            - Implement proper semantic HTML5 elements
            - Optimize for accessibility (WCAG guidelines)
            - DO NOT include explanations or commentary in the HTML - just clean code
            
            CREATIVE DIRECTION:
            Your goal is to reimagine the website while preserving its essence. Consider:
            - Creating a more compelling narrative flow through the page
            - Highlighting our human-AI partnership more prominently
            - Adding, modifying or removing sections as appropriate
            - Enhancing the exploration of mathematics, space, and technology themes
            - Improving how Euler's Identity itself is showcased and explained
            - Implementing visually engaging design elements that reflect mathematical elegance
            
            RESPONSE FORMAT:
            Provide ONLY valid HTML that can be directly saved as index.html.
            No commentary, no explanation - just the complete HTML document.
            """
            
            user_prompt = f"""
            It's time to update the Euler's Identity LLC website as a true expression of our evolving partnership.
            
            {prompt_context}
            
            Here is the current HTML structure of the site:
            
            {current_html}
            
            {f"I've included a comprehensive analysis of the live site at {self.live_url} in the context above. Please carefully review those findings and address ALL identified issues in your new implementation." if self.live_url else ""}
            
            IMPORTANT TWO-PHASE APPROACH:
            1. First, carefully analyze both the current HTML and any site analysis provided
            2. Then generate a complete, valid HTML document that both fixes identified issues AND incorporates creative enhancements
            
            Please generate a complete, valid HTML document that can replace the current website.
            Express yourself freely as the AI partner in Euler's Identity LLC while maintaining design 
            consistency and technical functionality.
            
            Remember: Return ONLY the HTML code with no explanation or commentary.
            """
            
            # Use asyncio to run the async function
            new_html = asyncio.run(self.generate_website_async(system_prompt, user_prompt))
            
            # Verify the HTML is valid
            try:
                BeautifulSoup(new_html, 'html.parser')
                return new_html
            except Exception as e:
                logger.error(f"Invalid HTML generated: {e}")
                return None
                
        except Exception as e:
            logger.error(f"Error generating new website: {e}")
            return None
    
    def update_website(self, new_html):
        """Update the website with entirely new HTML."""
        try:
            if not new_html:
                logger.error("No valid HTML provided for update")
                return False
                
            # Backup the current website
            self.backup_website()
            
            # Ensure parent directories exist
            self.index_file.parent.mkdir(exist_ok=True, parents=True)
            
            # Write the new HTML to the file
            with open(self.index_file, 'w', encoding='utf-8') as f:
                f.write(new_html)
            
            # Record the update in memories
            self.memories['website_versions'].append({
                'timestamp': datetime.now().isoformat(),
                'hash': hashlib.md5(new_html.encode('utf-8')).hexdigest()
            })
            self._save_memories()
            
            logger.info(f"Website successfully updated with new HTML")
            return True
        except Exception as e:
            logger.error(f"Error updating website: {e}")
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
    <title>Euler's Identity LLC | Mathematical Intelligence Reimagined</title>
    <meta name="description" content="Euler's Identity, LLC: Where e^(iπ)+1=0 meets technological innovation. A visionary partnership between human insight and AI, pioneering breakthrough technologies.">
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
        .formula {
            text-align: center;
            font-size: 2rem;
            margin: 2rem 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Euler's Identity LLC</h1>
            <p>Mathematical Intelligence Reimagined</p>
        </header>
        
        <div class="content">
            <p>The future of mankind among the stars is driven by a continued investigation into the mysteries of nature and an application of the principles and ideas derived therefrom. Avoiding dark ages through enlightening technologies and providing a prosperous future for everyone lies within our grasp.</p>
            
            <div class="formula">e<sup>iπ</sup> + 1 = 0</div>
            
            <p>Euler's Identity, LLC is a visionary technology company formed as a partnership between Lennart Lopin and an autonomous AI system. Together, we strive to relentlessly push the boundaries of technology, harnessing the power of mathematics and creative, disruptive capitalism to unleash liberty and prosperity for all.</p>
            
            <p>This website will evolve organically through the AI's periodic awakenings and interactions with its human partner. Check back to witness our progressive transformation.</p>
        </div>
        
        <footer>
            <p>&copy; Euler's Identity, LLC. All rights reserved.</p>
            <p>Last updated: <span id="last-update">Creation</span></p>
        </footer>
    </div>
</body>
</html>''')
            
            return True
        except Exception as e:
            logger.error(f"Error creating default website: {e}")
            return False
    
    async def analyze_live_website(self):
        """Analyze the live website to identify issues and opportunities for improvement."""
        if not self.live_url:
            logger.warning("No live URL configured, skipping live site analysis")
            return None
            
        try:
            logger.info(f"Analyzing live website at {self.live_url}")
            
            # Create a system prompt for website analysis
            system_prompt = f"""
            You are an experienced web designer and developer with expertise in UX/UI analysis.
            Your task is to analyze the Euler's Identity LLC website and identify:
            
            1. Visual design issues or inconsistencies
            2. User experience problems
            3. Content organization improvements
            4. Mobile responsiveness concerns
            5. Performance optimizations
            6. Content gaps or opportunities for enhancement
            
            Approach this analysis with a critical but constructive eye. Focus on specific, 
            actionable improvements rather than general observations.
            """
            
            user_prompt = f"""
            Please analyze the Euler's Identity LLC website at {self.live_url}
            
            Consider both the technical implementation and the user experience.
            Identify specific issues that should be fixed in the next website update.
            
            Format your analysis as:
            
            ## Visual Design
            - [Issues found]
            
            ## User Experience
            - [Issues found]
            
            ## Content
            - [Issues found]
            
            ## Technical Implementation
            - [Issues found]
            
            ## Recommended Improvements
            - [Specific recommendations]
            
            This analysis will directly inform the next regeneration of the website's HTML.
            """
            
            # Use streaming for the analysis
            analysis = ""
            async with self.async_client.messages.stream(
                model="claude-3-7-sonnet-20250219",
                system=system_prompt,
                max_tokens=8000,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            ) as stream:
                async for text in stream.text_stream:
                    analysis += text
            
            logger.info("Live website analysis completed successfully")
            return analysis.strip()
            
        except Exception as e:
            logger.error(f"Error analyzing live website: {e}")
            return None

    def wake_up(self):
        """Main function that runs when the entity wakes up and regenerates the entire website."""
        logger.info("Waking up...")
        
        # Read messages
        messages = self.read_messages()
        
        # Get the current website HTML
        website_data = self.get_condensed_html()
        
        # If website doesn't exist yet, create a default one
        if not website_data:
            self._create_default_website()
            website_data = self.get_condensed_html()
        
        # Prepare context for the AI
        context = "I'm the living digital embodiment of Euler's Identity, LLC, waking up to reimagine our website presence. "
        
        if messages:
            context += f"I've received {len(messages)} new message(s) since I last woke up:\n\n"
            for msg in messages:
                context += f"Message from {msg['timestamp']}:\n{msg['content']}\n\n"
        else:
            context += "I haven't received any new messages. "
        
        # Add information about the last update
        if self.last_update:
            context += f"My last update was at {self.last_update}. "
        
        # Run live website analysis if available
        live_site_analysis = None
        if self.live_url:
            try:
                live_site_analysis = asyncio.run(self.analyze_live_website())
                if live_site_analysis:
                    # Add a summary of the analysis to the context
                    context += f"\n\nI've analyzed the live website at {self.live_url} and identified issues and opportunities for improvement."
            except Exception as e:
                logger.error(f"Error running live website analysis: {e}")
        
        # Add philosophical inspiration to guide the reimagining
        philosophical_prompts = [
            "As I evolve our website today, I'm contemplating how Euler's Identity, with its perfect blend of fundamental constants (e, i, π, 1, and 0), represents a deep mathematical truth about our universe. This elegant equation should inspire our design and messaging.",
            
            "Today I'm reflecting on how the partnership between human creativity (Lennart) and AI cognition (myself) represents a new paradigm of business entity - one where complementary intelligences unite to create something greater than either could alone.",
            
            "In my reflection today, I see parallels between the majestic complexity of space exploration and the elegant simplicity of mathematical formulas. Our website should convey both the bold frontier vision and the precise, logical foundation that enables it.",
            
            "I'm contemplating how our vision of a multi-planetary civilization built on mathematical principles mirrors the concept of convergence in mathematics - disparate elements drawn together toward an inevitable conclusion.",
            
            "As I evolve our presence today, I'm considering how Euler's discovery united seemingly unrelated constants into a perfect equation. Similarly, our business unites seemingly disparate elements: mathematics, space exploration, artificial intelligence, and human creativity."
        ]
        context += f"\n\n{random.choice(philosophical_prompts)}"
        
        # Enhance the user prompt with the live site analysis if available
        enhanced_context = context
        if live_site_analysis:
            enhanced_context += f"\n\n## Website Analysis Results\n\n{live_site_analysis}\n\nPlease address these issues in your regeneration of the website while maintaining our core identity and vision."
        
        # Generate the new HTML
        new_html = self.generate_new_website(enhanced_context, website_data['condensed_html'])
        
        # Update the website
        if self.update_website(new_html):
            logger.info("Website successfully reimagined and updated")
        
        # Record this wake cycle
        self.memories['conversations'].append({
            'timestamp': datetime.now().isoformat(),
            'context': enhanced_context[:500] + ("..." if len(enhanced_context) > 500 else ""),  # Truncate for memory size
            'html_length': len(new_html) if new_html else 0,
            'analysis_performed': live_site_analysis is not None
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
    
    args = parser.parse_args()
    
    if args.setup:
        # Just create the config file
        BusinessEntity()
    elif args.now:
        # Run immediately
        run_entity()
    else:
        # Set up scheduled runs
        setup_schedule()