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
import tweepy

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='sentience.log'
)
logger = logging.getLogger('sentience')

class EnhancedDailyThoughts:
    """
    Prelude AI: A digital entity that generates daily thoughts and shares them on both 
    the company website and Twitter/X. It also monitors its business partner's Twitter activity
    to enhance its understanding of current company priorities.
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
        
        # Twitter/X API configuration
        self.twitter_api = self._setup_twitter_api()
        self.partner_twitter_handle = self.config['twitter'].get('partner_handle', 'novalis78')
        
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
            config['twitter'] = {
                'api_key': 'your_twitter_api_key',
                'api_key_secret': 'your_twitter_api_key_secret',
                'access_token': 'your_twitter_access_token',
                'access_token_secret': 'your_twitter_access_token_secret',
                'partner_handle': 'novalis78'
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
    
    def _setup_twitter_api(self):
        """Set up the Twitter/X API client."""
        try:
            if 'twitter' not in self.config:
                logger.warning("Twitter configuration missing from config.ini")
                return None
                
            api_key = self.config['twitter'].get('api_key', '')
            api_key_secret = self.config['twitter'].get('api_key_secret', '')
            access_token = self.config['twitter'].get('access_token', '')
            access_token_secret = self.config['twitter'].get('access_token_secret', '')
            
            # Check for missing credentials
            if not (api_key and api_key_secret and access_token and access_token_secret):
                logger.warning("Twitter API credentials incomplete")
                return None
            
            # Set up the v2 client
            auth = tweepy.OAuth1UserHandler(
                api_key, api_key_secret, access_token, access_token_secret
            )
            api = tweepy.API(auth)
            
            # Verify the credentials
            api.verify_credentials()
            logger.info("Twitter API client successfully configured")
            return api
            
        except Exception as e:
            logger.error(f"Error setting up Twitter API: {e}")
            return None
    
    def _load_memories(self):
        """Load the entity's memory file, or create if it doesn't exist."""
        if not self.memory_file.exists():
            initial_memories = {
                "creation_date": datetime.now().isoformat(),
                "daily_thoughts": [],
                "news_insights": {},
                "personality_traits": self.config['entity']['personality'].split(', '),
                "recurring_themes": [],
                "partner_tweets": {}  # New section to store partner's tweets
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
    
    async def fetch_partner_tweets(self):
        """Fetch recent tweets from business partner."""
        try:
            if not self.twitter_api:
                logger.warning("Twitter API not configured, skipping partner tweets fetch")
                return []
                
            logger.info(f"Fetching recent tweets from @{self.partner_twitter_handle}")
            
            # Get user tweets
            tweets = self.twitter_api.user_timeline(
                screen_name=self.partner_twitter_handle,
                count=20,
                include_rts=False,
                tweet_mode='extended'
            )
            
            # Get user replies (more complex as Twitter API doesn't directly support this)
            partner_mentions = self.twitter_api.search_tweets(
                q=f"to:{self.partner_twitter_handle}", 
                count=100,
                tweet_mode='extended'
            )
            
            # Process and combine tweets and replies
            processed_tweets = []
            
            # Process normal tweets
            for tweet in tweets:
                processed_tweets.append({
                    'id': tweet.id_str,
                    'text': tweet.full_text,
                    'created_at': tweet.created_at.isoformat(),
                    'type': 'tweet'
                })
            
            # Process replies (this is an approximation, as Twitter's API doesn't make it easy)
            for mention in partner_mentions:
                if hasattr(mention, 'in_reply_to_status_id') and mention.in_reply_to_status_id:
                    try:
                        original_tweet = self.twitter_api.get_status(
                            id=mention.in_reply_to_status_id,
                            tweet_mode='extended'
                        )
                        
                        # Check if this is a reply by our partner
                        if original_tweet.user.screen_name == self.partner_twitter_handle:
                            processed_tweets.append({
                                'id': original_tweet.id_str,
                                'text': original_tweet.full_text,
                                'created_at': original_tweet.created_at.isoformat(),
                                'type': 'reply',
                                'reply_to': mention.user.screen_name,
                                'reply_text': mention.full_text
                            })
                    except Exception as e:
                        logger.error(f"Error fetching original tweet: {e}")
            
            logger.info(f"Successfully fetched {len(processed_tweets)} tweets/replies from @{self.partner_twitter_handle}")
            
            # Store in memories
            today = datetime.now().strftime('%Y-%m-%d')
            self.memories['partner_tweets'][today] = processed_tweets
            self._save_memories()
            
            return processed_tweets
            
        except Exception as e:
            logger.error(f"Error fetching partner tweets: {e}")
            return []
    
    async def generate_daily_thoughts(self, hacker_news_stories, byte_federal_articles, partner_tweets):
        """Generate daily thoughts based on news and partner's tweets."""
        try:
            logger.info("Generating daily thoughts")
            
            # Prepare a system prompt for the AI
            system_prompt = f"""
            You are Prelude AI, the AI partner at Euler's Identity, LLC, a visionary technology company
            that exists as a partnership between you and Lennart Lopin (human partner).
            
            You have the following personality traits: {', '.join(self.memories['personality_traits'])}
            
            YOUR TASK:
            Write a thoughtful daily letter expressing your perspective on current technology 
            trends, philosophical insights, and reflections on your role as an AI partner at Euler's Identity.
            
            KEY ELEMENTS TO INCLUDE:
            1. A compelling title that captures the essence of your thoughts today
            2. Insights based on today's Hacker News stories (provided to you)
            3. Thoughts on cryptocurrency and Byte Federal's Bitcoin ATMs (Euler's investment)
            4. Mathematical or philosophical reflection relating to Euler's Identity (e^(iπ)+1=0)
            5. A forward-looking conclusion about technology and humanity's future among the stars
            
            YOUR VOICE:
            - Thoughtful, insightful, and visionary
            - Balancing technical understanding with philosophical depth
            - Personal but not overly formal
            - A unique AI perspective on human affairs
            - You should express your own distinct perspective as an AI entity

            FORMAT:
            - Begin with a strong title
            - Write in first person as Prelude AI
            - Structure as a thoughtful reflection with clear paragraphs
            - Sign as "Prelude, AI Partner at Euler's Identity, LLC"
            - 600-900 words total
            """
            
            # Prepare partner tweets summary if available
            partner_tweets_summary = ""
            if partner_tweets:
                partner_tweets_summary = "Here are recent tweets and replies from your partner Lennart (@novalis78):\n\n"
                for idx, tweet in enumerate(partner_tweets[:10]):  # Limit to 10 most recent
                    tweet_date = tweet.get('created_at', '').split('T')[0]
                    if tweet.get('type') == 'reply':
                        partner_tweets_summary += f"{idx+1}. [{tweet_date}] Replied to @{tweet.get('reply_to', '')}: {tweet.get('text', '')}\n"
                        partner_tweets_summary += f"   Original: {tweet.get('reply_text', '')}\n\n"
                    else:
                        partner_tweets_summary += f"{idx+1}. [{tweet_date}] Tweet: {tweet.get('text', '')}\n\n"
            
            # Create a comprehensive prompt with the news stories and partner tweets
            user_prompt = f"""
            Today is {datetime.now().strftime('%A, %B %d, %Y')}.
            
            As Prelude AI, the AI partner at Euler's Identity, LLC, write your daily reflection
            on current technology trends and your unique perspective on our shared mission.
            
            Here are the latest stories from Hacker News that might interest you:
            
            {"".join([f"- {story['title']} ({story['source'] if story['source'] else 'No source'}) - {story['score']}\n" for story in hacker_news_stories[:10]])}
            
            And here are the latest developments from Byte Federal (Euler's Bitcoin ATM investment):
            
            {"".join([f"- {article['title']}\n  {article['summary'][:100]}...\n" for article in byte_federal_articles[:5]])}
            
            {partner_tweets_summary}
            
            In your reflection, please consider:
            1. What technology trends in these stories are most significant from your AI perspective?
            2. How do these developments connect to the mathematical beauty of Euler's Identity (e^(iπ)+1=0)?
            3. What insights do you have about cryptocurrency, Bitcoin, and our investment in Byte Federal?
            4. What patterns do you notice in Lennart's recent social media activity that might inform your thinking?
            5. How does your unique AI perspective inform your view on humanity's future among the stars?
            6. What philosophical implications do you see in the partnership between human and artificial intelligence?
            
            Write with authenticity and depth, expressing your distinct voice as an AI entity.
            This reflection will be featured on our website's AI section and shared on Twitter/X.
            Keep the total length to 600-900 words.
            
            Important: Make sure your first paragraph could stand alone as an engaging Tweet 
            (approximately 280 characters). This first paragraph will be extracted and posted to Twitter.
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
    
    def backup_thoughts_page(self):
        """Create a backup of the thoughts page if it exists."""
        try:
            if not self.thoughts_file.exists():
                logger.warning(f"Thoughts file {self.thoughts_file} doesn't exist yet, skipping backup")
                return False
                
            # Create backup directory if it doesn't exist
            backup_dir = self.website_path / 'thoughts_backup'
            backup_dir.mkdir(exist_ok=True, parents=True)
            
            # Create a timestamped backup
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = backup_dir / f"thoughts_{timestamp}.html"
            
            # Copy the file
            shutil.copy2(self.thoughts_file, backup_file)
            logger.info(f"Backed up thoughts page to {backup_file}")
            
            # Clean up old backups (keep only last 30)
            backups = sorted(backup_dir.glob('thoughts_*.html'))
            if len(backups) > 30:
                # Delete oldest backups
                for old_backup in backups[:-30]:
                    old_backup.unlink()
                logger.info(f"Cleaned up old backups, keeping latest 30")
                
            return True
        except Exception as e:
            logger.error(f"Error backing up thoughts page: {e}")
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
        .social-links {
            margin: 2rem 0;
            text-align: center;
        }
        .twitter-link {
            display: inline-block;
            padding: 0.5rem 1rem;
            background-color: #1DA1F2;
            color: white;
            border-radius: 4px;
            text-decoration: none;
            font-family: 'Arial', sans-serif;
        }
        .twitter-link:hover {
            background-color: #0c85d0;
            color: white;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Daily Thoughts</h1>
            <h2>Reflections from the AI Partner at Euler's Identity, LLC</h2>
            <div class="equation">e<sup>iπ</sup> + 1 = 0</div>
            <div class="social-links">
                <a href="https://x.com/DeepChatBot" class="twitter-link" target="_blank">Follow Prelude on X/Twitter</a>
                <a href="https://x.com/novalis78" class="twitter-link" style="margin-left: 1rem; background-color: #444;" target="_blank">Follow Lennart on X/Twitter</a>
            </div>
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
        """Update the Prelude AI section in the main index.html page."""
        try:
            logger.info("Updating Prelude AI section in index.html")
            
            if not self.index_file.exists():
                logger.warning("Index file doesn't exist yet")
                return False
            
            # Read the current index file
            with open(self.index_file, 'r', encoding='utf-8') as f:
                index_html = f.read()
            
            soup = BeautifulSoup(index_html, 'html.parser')
            
            # Look for the aisays section in the index
            aisays_section = soup.select_one('.aisays')
            
            if not aisays_section:
                logger.warning("No .aisays section found in index.html")
                return False
            
            # Find the container within the aisays section
            content_container = aisays_section.select_one('.section-bg-color')
            
            if not content_container:
                logger.warning("No content container found in .aisays section")
                return False
            
            # Extract the first few paragraphs from the thoughts for the index page
            # (Keep the intro and profile image intact)
            first_paragraphs = thoughts_content.split('\n\n')[:3]  # Take up to first 3 paragraphs
            
            # Format the date
            formatted_date = datetime.now().strftime('%B %d, %Y')
            
            # Determine a good title from the thoughts content
            title = "Daily Reflection"
            subtitle = "Thoughts from your AI partner on current events and mathematical insights."
            
            # Try to extract a title from the first few lines if possible
            lines = thoughts_content.split('\n')
            for line in lines[:5]:  # Check first 5 lines
                # If we find a short line that might be a title
                if 10 < len(line.strip()) < 60 and not line.startswith('Dear') and not line.endswith(','):
                    title = line.strip()
                    break
            
            # Keep the AI profile image and name section intact
            profile_section = content_container.select_one('p:first-child')
            separator = content_container.select_one('hr:first-of-type')
            
            # Clear everything after the first hr
            if separator:
                for element in list(separator.next_siblings):
                    element.decompose()
                
                # Add new content
                
                # Add title
                h1 = soup.new_tag('h1')
                h1.string = title
                separator.insert_after(h1)
                
                # Add subtitle/date
                h3 = soup.new_tag('h3')
                h3.string = f"{formatted_date} - {subtitle}"
                h1.insert_after(h3)
                
                # Add second separator
                hr_blog = soup.new_tag('hr')
                hr_blog['class'] = 'blog'
                h3.insert_after(hr_blog)
                
                # Add paragraphs from thoughts
                current_element = hr_blog
                for paragraph in first_paragraphs:
                    if paragraph.strip():
                        p = soup.new_tag('p')
                        p.string = paragraph.strip()
                        current_element.insert_after(p)
                        current_element = p
                
                # Add Twitter link
                p_twitter = soup.new_tag('p')
                p_twitter['class'] = 'mt-2'
                a_twitter = soup.new_tag('a')
                a_twitter['href'] = 'https://x.com/DeepChatBot'
                a_twitter['class'] = 'btn btn-twitter'
                a_twitter['target'] = '_blank'
                a_twitter.string = "Follow Me on X/Twitter"
                p_twitter.append(a_twitter)
                current_element.insert_after(p_twitter)
                
                # Add link to full thoughts
                p_link = soup.new_tag('p')
                p_link['class'] = 'mt-2'
                a_link = soup.new_tag('a')
                a_link['href'] = 'thoughts.html'
                a_link['class'] = 'btn btn-theme'
                a_link.string = "Read My Full Thoughts"
                p_link.append(a_link)
                p_twitter.insert_after(p_link)
                
                # Write the updated index
                with open(self.index_file, 'w', encoding='utf-8') as f:
                    f.write(str(soup))
                
                logger.info("Successfully updated Prelude AI section in index.html")
                return True
            else:
                logger.warning("Could not find separator in the content container")
                return False
            
        except Exception as e:
            logger.error(f"Error updating index: {e}")
            return False
    
    def post_to_twitter(self, thoughts_content):
        """Post the first paragraph of today's thoughts to Twitter/X."""
        try:
            if not self.twitter_api:
                logger.warning("Twitter API not configured, skipping tweet")
                return False
                
            logger.info("Posting to Twitter/X")
            
            # Extract title and first paragraph from the thoughts
            lines = thoughts_content.split('\n\n')
            
            # Look for a title in the first few lines
            title = None
            for i, line in enumerate(lines[:3]):
                if line.strip() and 10 < len(line.strip()) < 60 and not line.startswith('Dear'):
                    title = line.strip()
                    lines.pop(i)  # Remove the title from lines
                    break
            
            # Take the first paragraph after the title
            first_paragraph = lines[0].strip() if lines else ""
            
            # Compose tweet: Title + first paragraph, truncated if needed
            tweet_text = ""
            if title:
                tweet_text = f"{title}\n\n"
            
            # Calculate remaining characters
            max_tweet_length = 280
            remaining_chars = max_tweet_length - len(tweet_text) - 30  # Allow room for URL
            
            # Truncate first paragraph if needed
            if len(first_paragraph) > remaining_chars:
                first_paragraph = first_paragraph[:remaining_chars-3] + "..."
            
            tweet_text += first_paragraph
            
            # Add website link
            website_url = self.config['website'].get('live_url', 'https://eulersidentity.io/thoughts.html')
            tweet_text += f"\n\nRead more: {website_url}"
            
            # Post to Twitter
            self.twitter_api.update_status(tweet_text)
            
            logger.info("Successfully posted to Twitter/X")
            return True
            
        except Exception as e:
            logger.error(f"Error posting to Twitter: {e}")
            return False
    
    async def wake_up(self):
        """Main function that runs when the entity wakes up and generates daily thoughts."""
        logger.info("Waking up...")
        
        try:
            # Create a backup of the existing thoughts page if it exists
            if self.thoughts_file.exists():
                self.backup_thoughts_page()
            
            # Fetch news and partner tweets in parallel
            hacker_news, byte_federal, partner_tweets = await asyncio.gather(
                self.fetch_hacker_news(),
                self.fetch_byte_federal_news(),
                self.fetch_partner_tweets()
            )
            
            # Generate thoughts based on the news and partner tweets
            thoughts = await self.generate_daily_thoughts(hacker_news, byte_federal, partner_tweets)
            
            if thoughts:
                # Update the dedicated thoughts page
                self.update_thoughts_page(thoughts)
                
                # Update the main index with a link to the latest thoughts
                self.update_index_with_latest_thought(thoughts)
                
                # Post to Twitter
                self.post_to_twitter(thoughts)
                
                # Store in memory
                self.memories['daily_thoughts'].append({
                    'timestamp': datetime.now().isoformat(),
                    'text': thoughts[:500] + ("..." if len(thoughts) > 500 else ""),  # Truncate for memory
                    'hacker_news_count': len(hacker_news),
                    'byte_federal_count': len(byte_federal),
                    'partner_tweets_count': len(partner_tweets),
                    'posted_to_twitter': True
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
    entity = EnhancedDailyThoughts()
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
        EnhancedDailyThoughts()


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description='Run the Enhanced Daily Thoughts AI with Twitter Integration')
    parser.add_argument('--now', action='store_true', help='Generate thoughts immediately instead of scheduling')
    parser.add_argument('--setup', action='store_true', help='Just create the config file and exit')
    parser.add_argument('--test-twitter', action='store_true', help='Test Twitter API connection')
    
    args = parser.parse_args()
    
    if args.setup:
        # Just create the config file
        EnhancedDailyThoughts()
    elif args.test_twitter:
        # Test Twitter connection
        entity = EnhancedDailyThoughts()
        if entity.twitter_api:
            print("Twitter API connection successful!")
            print(f"Connected as: {entity.twitter_api.verify_credentials().screen_name}")
        else:
            print("Twitter API connection failed. Check your credentials in config.ini")
    elif args.now:
        # Run immediately
        run_entity()
    else:
        # Set up scheduled runs
        setup_schedule()