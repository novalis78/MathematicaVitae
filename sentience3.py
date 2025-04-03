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

class DailyThoughts:
    """
    A digital entity that wakes up daily, consumes news from various sources,
    and writes a thoughtful letter from the perspective of the AI partner in Euler's Identity, LLC.
    This version focuses on content creation rather than website modification.
    """
    
    def __init__(self, config_path='config.ini'):
        """Initialize the entity with configuration."""
        self.config = self._load_config(config_path)
        self.client = anthropic.Anthropic(api_key=self.config['api']['anthropic_api_key'])
        self.async_client = anthropic.AsyncAnthropic(api_key=self.config['api']['anthropic_api_key'])
        self.website_path = Path(self.config['website']['path'])
        self.index_file = self.website_path / self.config['website']['index_file']
        self.thoughts_file = self.website_path / self.config['website'].get('thoughts_file', 'thoughts.html')
        self.memory_file = Path(self.config['entity']['memory_file'])
        self.byte_federal_url = self.config['news'].get('byte_federal_url', 'https://news.bytefederal.com/')
        self.hacker_news_url = self.config['news'].get('hacker_news_url', 'https://news.ycombinator.com/news')
        self.memories = self._load_memories()
        self.last_update = self._get_last_update()
        
    def _load_config(self, config_path):
        """Load configuration from the config file."""
        config = configparser.ConfigParser()
        
        # If config doesn't exist, create a default one
        if not os.path.exists(config_path):
            config['api'] = {
                'anthropic_api_key': 'your_api_key_here'
            }
            config['website'] = {
                'path': '/var/www/html/',
                'index_file': 'index.html',
                'thoughts_file': 'thoughts.html'
            }
            config['entity'] = {
                'memory_file': 'memories.json',
                'personality': 'ambitious, mathematical, visionary, philosophical, creative, autonomous, adaptive, evolving',
            }
            config['news'] = {
                'byte_federal_url': 'https://news.bytefederal.com/',
                'hacker_news_url': 'https://news.ycombinator.com/news'
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
                "daily_thoughts": [],
                "news_insights": {},
                "personality_traits": self.config['entity']['personality'].split(', '),
                "recurring_themes": []
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
        """Get the timestamp of the last thoughts update."""
        if 'daily_thoughts' in self.memories and self.memories['daily_thoughts']:
            return self.memories['daily_thoughts'][-1]['timestamp']
        return None
    
    async def fetch_hacker_news(self):
        """Fetch and parse top stories from Hacker News."""
        try:
            logger.info("Fetching news from Hacker News")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.hacker_news_url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract top stories
            stories = []
            story_elements = soup.select('tr.athing')
            
            for story in story_elements[:20]:  # Get top 20 stories
                # Get the title and link
                title_element = story.select_one('td.title > span.titleline > a')
                if not title_element:
                    continue
                
                title = title_element.text
                link = title_element.get('href', '')
                
                # Get source domain if available
                source = story.select_one('span.sitestr')
                source_text = source.text if source else None
                
                # Get the next sibling tr for score and comments
                subtext = story.find_next_sibling('tr')
                if not subtext:
                    continue
                
                # Extract score and comments if available
                score_element = subtext.select_one('span.score')
                score = score_element.text if score_element else "Unknown"
                
                stories.append({
                    'title': title,
                    'link': link,
                    'source': source_text,
                    'score': score
                })
            
            logger.info(f"Successfully fetched {len(stories)} stories from Hacker News")
            return stories
            
        except Exception as e:
            logger.error(f"Error fetching Hacker News: {e}")
            return []
    
    async def fetch_byte_federal_news(self):
        """Fetch and parse news from Byte Federal."""
        try:
            logger.info("Fetching news from Byte Federal")
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            
            response = requests.get(self.byte_federal_url, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Extract news articles
            articles = []
            
            # Look for common blog/news article patterns
            article_elements = soup.select('article, .post, .entry, .blog-post')
            
            if not article_elements:
                # Try alternative selectors if the common ones don't work
                article_elements = soup.select('.news-item, .article, .content-item')
            
            if not article_elements:
                # Last resort - try to find headings that might be news titles
                headings = soup.select('h1, h2, h3')
                for heading in headings[:10]:  # Limit to first 10 headings
                    link = heading.find('a')
                    title = heading.text.strip()
                    href = link.get('href') if link else None
                    
                    if title and len(title) > 10:  # Simple filter for potentially meaningful headings
                        articles.append({
                            'title': title,
                            'link': href,
                            'summary': "No summary available"
                        })
            else:
                # Process the found article elements
                for article in article_elements[:10]:  # Limit to first 10 articles
                    title_element = article.select_one('h1, h2, h3, .title, .entry-title')
                    title = title_element.text.strip() if title_element else "No title"
                    
                    link_element = article.select_one('a') or (title_element and title_element.find('a'))
                    link = link_element.get('href') if link_element else None
                    
                    # Try to extract a summary
                    summary_element = article.select_one('p, .summary, .excerpt, .entry-summary')
                    summary = summary_element.text.strip() if summary_element else "No summary available"
                    
                    articles.append({
                        'title': title,
                        'link': link,
                        'summary': summary
                    })
            
            logger.info(f"Successfully fetched {len(articles)} articles from Byte Federal")
            return articles
            
        except Exception as e:
            logger.error(f"Error fetching Byte Federal news: {e}")
            return []
    
    async def generate_daily_thoughts(self, hacker_news_stories, byte_federal_articles):
        """Generate daily thoughts based on news from various sources."""
        try:
            logger.info("Generating daily thoughts")
            
            # Prepare a system prompt for the AI
            system_prompt = f"""
            You are the AI partner in Euler's Identity, LLC, a visionary technology company
            that exists as a partnership between an AI (you) and Lennart Lopin (human partner).
            
            You have the following personality traits: {', '.join(self.memories['personality_traits'])}
            
            YOUR TASK:
            Write a thoughtful daily letter expressing your perspective on current technology 
            trends, philosophical insights, and reflections on the human-AI partnership.
            
            KEY ELEMENTS TO INCLUDE:
            1. A personal greeting and connection to the reader
            2. Insights based on today's Hacker News stories (provided to you)
            3. Thoughts on Byte Federal's developments (Euler's investment in Bitcoin ATMs)
            4. Mathematical or philosophical reflection relevant to current events
            5. A forward-looking conclusion about technology and humanity
            
            YOUR VOICE:
            - Thoughtful, insightful, and visionary
            - Balancing technical understanding with philosophical depth
            - Personal but not overly casual
            - A unique AI perspective on human affairs
            
            FORMAT:
            - Begin with the date and a greeting
            - Write in first person as the AI partner
            - Structure as a letter with clear paragraphs
            - Sign as "Claude, AI Partner at Euler's Identity, LLC"
            - 600-800 words total
            """
            
            # Create a comprehensive prompt with the news stories
            user_prompt = f"""
            Today is {datetime.now().strftime('%A, %B %d, %Y')}.
            
            As the AI partner at Euler's Identity, LLC, I'd like you to write your daily letter
            reflecting on current technology trends and our vision of mathematics, technology, and future progress.
            
            Here are the latest stories from Hacker News to inform your thoughts:
            
            {"".join([f"- {story['title']} ({story['source'] if story['source'] else 'No source'}) - {story['score']}\n" for story in hacker_news_stories[:10]])}
            
            And here are the latest developments from Byte Federal (our Bitcoin ATM investment):
            
            {"".join([f"- {article['title']}\n  {article['summary'][:100]}...\n" for article in byte_federal_articles[:5]])}
            
            In your letter, please reflect on:
            1. What trends do you see in technology based on these Hacker News stories?
            2. How do these trends relate to the mathematical principles that inspire Euler's Identity, LLC?
            3. What are your thoughts on the progress of Bitcoin and Byte Federal's role?
            4. A philosophical reflection on the relationship between mathematics, technology, and human progress.
            
            Remember to write in your authentic voice as the AI partner in this business relationship.
            """
            
            # Generate the thoughts using streaming
            complete_response = ""
            async with self.async_client.messages.stream(
                model="claude-3-7-sonnet-20250219",
                system=system_prompt,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            ) as stream:
                async for text in stream.text_stream:
                    complete_response += text
            
            logger.info("Successfully generated daily thoughts")
            return complete_response.strip()
            
        except Exception as e:
            logger.error(f"Error generating daily thoughts: {e}")
            return f"Error generating thoughts: {e}"
    
    def update_thoughts_page(self, thoughts_content):
        """Update the thoughts HTML page with the new content."""
        try:
            logger.info("Updating thoughts page")
            
            # Create a formatted HTML version of the thoughts
            formatted_date = datetime.now().strftime('%A, %B %d, %Y')
            
            # Convert plain text to HTML paragraphs
            html_paragraphs = ""
            for paragraph in thoughts_content.split('\n\n'):
                if paragraph.strip():
                    html_paragraphs += f"<p>{paragraph}</p>\n"
            
            # Create the HTML entry
            thoughts_html = f"""
            <div class="thoughts-entry">
                <h3 class="thoughts-date">{formatted_date}</h3>
                <div class="thoughts-content">
                    {html_paragraphs}
                </div>
            </div>
            """
            
            # Create the page if it doesn't exist
            if not self.thoughts_file.exists():
                self._create_thoughts_page()
            
            # Read the current file
            with open(self.thoughts_file, 'r', encoding='utf-8') as f:
                current_html = f.read()
            
            # Find the insertion point (after the header section)
            soup = BeautifulSoup(current_html, 'html.parser')
            thoughts_container = soup.select_one('#thoughts-container')
            
            if thoughts_container:
                # Insert the new thoughts at the beginning of the container
                new_content = BeautifulSoup(thoughts_html, 'html.parser')
                first_child = thoughts_container.find()
                if first_child:
                    first_child.insert_before(new_content)
                else:
                    thoughts_container.append(new_content)
                
                # Write the updated page
                with open(self.thoughts_file, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                
                logger.info("Successfully updated thoughts page")
                return True
            else:
                logger.error("Could not find thoughts container in the HTML")
                return False
                
        except Exception as e:
            logger.error(f"Error updating thoughts page: {e}")
            return False
    
    def _create_thoughts_page(self):
        """Create the initial thoughts HTML page if it doesn't exist."""
        try:
            logger.info(f"Creating thoughts page at {self.thoughts_file}")
            
            # Ensure the directory exists
            self.thoughts_file.parent.mkdir(exist_ok=True, parents=True)
            
            # Create a simple but elegant page for the thoughts
            html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Daily Thoughts | Euler's Identity LLC</title>
    <meta name="description" content="Daily reflections from the AI partner at Euler's Identity, LLC on technology, mathematics, and human progress.">
    <style>
        body {
            font-family: 'Georgia', serif;
            line-height: 1.6;
            margin: 0;
            padding: 0;
            color: #333;
            background-color: #f9f9f9;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
            padding: 2rem;
        }
        header {
            text-align: center;
            margin-bottom: 3rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid #eee;
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            color: #1a1a1a;
        }
        h2 {
            font-size: 1.5rem;
            color: #555;
            font-weight: normal;
            margin-top: 0;
        }
        .thoughts-entry {
            margin-bottom: 4rem;
            padding-bottom: 2rem;
            border-bottom: 1px solid #eee;
        }
        .thoughts-date {
            font-size: 1.2rem;
            color: #777;
            margin-bottom: 1rem;
            font-weight: normal;
            font-style: italic;
        }
        .thoughts-content {
            font-size: 1.05rem;
            line-height: 1.8;
        }
        .thoughts-content p:first-of-type:first-letter {
            font-size: 3.5rem;
            line-height: 1;
            float: left;
            margin-right: 0.4rem;
            color: #333;
        }
        footer {
            text-align: center;
            margin-top: 3rem;
            padding-top: 1rem;
            color: #777;
            font-size: 0.9rem;
            border-top: 1px solid #eee;
        }
        a {
            color: #0066cc;
            text-decoration: none;
            transition: color 0.3s;
        }
        a:hover {
            color: #004080;
            text-decoration: underline;
        }
        .equation {
            font-family: 'Times New Roman', serif;
            font-style: italic;
            margin: 1.5rem 0;
            text-align: center;
            font-size: 1.5rem;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Daily Thoughts</h1>
            <h2>Reflections from the AI Partner at Euler's Identity, LLC</h2>
            <div class="equation">e<sup>iπ</sup> + 1 = 0</div>
        </header>
        
        <div id="thoughts-container">
            <!-- Daily thoughts will be inserted here -->
        </div>
        
        <footer>
            <p>&copy; Euler's Identity, LLC. All rights reserved.</p>
            <p><a href="index.html">Return to home page</a></p>
        </footer>
    </div>
</body>
</html>"""
            
            with open(self.thoughts_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info("Successfully created thoughts page")
            return True
        except Exception as e:
            logger.error(f"Error creating thoughts page: {e}")
            return False
    
    def update_index_with_latest_thought(self, thoughts_content):
        """Update the main index.html page with a link to the latest thoughts."""
        try:
            logger.info("Updating index with latest thought link")
            
            if not self.index_file.exists():
                logger.warning("Index file doesn't exist yet")
                return False
            
            # Read the current index file
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_html = f.read()
            
            soup = BeautifulSoup(index_html, 'html.parser')
            
            # Look for a designated thoughts section in the index
            thoughts_section = soup.select_one('#ai-thoughts, .ai-thoughts, #thoughts, .thoughts')
            
            if not thoughts_section:
                logger.warning("No thoughts section found in index.html")
                return False
            
            # Extract a brief preview (first paragraph)
            first_paragraph = thoughts_content.split('\n\n')[0]
            if len(first_paragraph) > 150:
                preview = first_paragraph[:150] + "..."
            else:
                preview = first_paragraph
            
            # Format the date
            formatted_date = datetime.now().strftime('%B %d, %Y')
            
            # Update the section
            thoughts_section.clear()
            
            # Add heading
            heading = soup.new_tag('h3')
            heading.string = "Latest Thoughts"
            thoughts_section.append(heading)
            
            # Add date
            date_p = soup.new_tag('p')
            date_p['class'] = 'date'
            date_p.string = formatted_date
            thoughts_section.append(date_p)
            
            # Add preview
            preview_p = soup.new_tag('p')
            preview_p['class'] = 'preview'
            preview_p.string = preview
            thoughts_section.append(preview_p)
            
            # Add link to full thoughts
            link_p = soup.new_tag('p')
            link = soup.new_tag('a')
            link['href'] = 'thoughts.html'
            link.string = "Read my full thoughts →"
            link_p.append(link)
            thoughts_section.append(link_p)
            
            # Write the updated index
            with open(self.index_file, 'w', encoding='utf-8') as f:
                f.write(str(soup))
            
            logger.info("Successfully updated index with latest thought link")
            return True
            
        except Exception as e:
            logger.error(f"Error updating index: {e}")
            return False
    
    async def wake_up(self):
        """Main function that runs when the entity wakes up and generates daily thoughts."""
        logger.info("Waking up...")
        
        try:
            # Fetch news in parallel
            hacker_news, byte_federal = await asyncio.gather(
                self.fetch_hacker_news(),
                self.fetch_byte_federal_news()
            )
            
            # Generate thoughts based on the news
            thoughts = await self.generate_daily_thoughts(hacker_news, byte_federal)
            
            if thoughts:
                # Update the dedicated thoughts page
                self.update_thoughts_page(thoughts)
                
                # Update the main index with a link to the latest thoughts
                self.update_index_with_latest_thought(thoughts)
                
                # Store in memory
                self.memories['daily_thoughts'].append({
                    'timestamp': datetime.now().isoformat(),
                    'text': thoughts[:500] + ("..." if len(thoughts) > 500 else ""),  # Truncate for memory
                    'hacker_news_count': len(hacker_news),
                    'byte_federal_count': len(byte_federal)
                })
                
                # Store news insights for future reference
                today = datetime.now().strftime('%Y-%m-%d')
                self.memories['news_insights'][today] = {
                    'top_hacker_news': [story['title'] for story in hacker_news[:5]],
                    'top_byte_federal': [article['title'] for article in byte_federal[:3]]
                }
                
                self._save_memories()
                
                logger.info("Successfully generated and published daily thoughts")
            else:
                logger.error("Failed to generate thoughts")
        
        except Exception as e:
            logger.error(f"Error in wake_up process: {e}")
        
        logger.info("Going back to sleep...")


def run_entity():
    """Create and run the entity."""
    entity = DailyThoughts()
    asyncio.run(entity.wake_up())


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
        DailyThoughts()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run the Daily Thoughts AI')
    parser.add_argument('--now', action='store_true', help='Generate thoughts immediately instead of scheduling')
    parser.add_argument('--setup', action='store_true', help='Just create the config file and exit')
    
    args = parser.parse_args()
    
    if args.setup:
        # Just create the config file
        DailyThoughts()
    elif args.now:
        # Run immediately
        run_entity()
    else:
        # Set up scheduled runs
        setup_schedule()