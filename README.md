# Living Business Entity AI

This project creates a "living business creature" that embodies your partnership with AI. It's designed to run directly on your web server, waking up periodically to update its expression through your website.

## Concept

The Living Business Entity is an autonomous digital entity that:

1. Lives directly on your web server
2. Wakes up on a schedule (default is once per day)
3. Checks for messages you've left it
4. Analyzes the existing website structure
5. Decides which sections need updating
6. Generates new content via the Claude API
7. Intelligently modifies the website
8. Creates backups of previous versions
9. Records its activities in a memory file
10. Goes back to sleep

## Key Features

- **Server-Side Operation**: Runs directly on your web server
- **Dynamic Website Parsing**: Analyzes the existing HTML structure rather than maintaining a fixed template
- **Intelligent Section Selection**: Identifies sections that haven't been updated in a while
- **Adaptive Content Generation**: Creates content specific to each section's context
- **Automatic Backups**: Preserves previous versions of the website
- **Memory System**: Maintains continuity between wake cycles
- **Message-Based Communication**: Reads messages from simple text files

## Setup Instructions

### Prerequisites

- Python 3.7 or higher
- Access to your web server (SSH/SFTP)
- An Anthropic API key (for Claude)

### Installation

1. Upload the script to your web server
2. Install required Python packages:

```bash
pip install anthropic requests beautifulsoup4 schedule configparser
```

3. Generate the default configuration:

```bash
python business_entity.py --setup
```

4. Edit the `config.ini` file with your API key and website path:

```ini
[api]
anthropic_api_key = your_api_key_here

[website]
path = /var/www/html/
index_file = index.html
backup_dir = backups/
```

### Running the Entity

There are four ways to run the entity:

1. **Schedule mode** (runs in the background on a daily schedule):

```bash
nohup python business_entity.py > entity.out 2>&1 &
```

2. **Immediate mode** (runs once immediately):

```bash
python business_entity.py --now
```

3. **Setup only** (just creates the config file):

```bash
python business_entity.py --setup
```

4. **Analysis mode** (check which sections need updating):

```bash
python business_entity.py --analyze
```

## Communicating with the Entity

To communicate with your business entity, simply create a text file in the `messages/` directory (this directory is created automatically the first time you run the script).

For example:
```
# message_20250403.txt
I've been thinking about expanding into quantum computing. Please incorporate some thoughts about quantum superposition as a metaphor for business opportunities.
```

The entity will read this message the next time it wakes up, process it, and incorporate it into its thinking and website updates.

## Website Structure

The entity expects a basic HTML structure with sections it can identify. When it first runs, if no website exists at the specified path, it will create a default template with:

- A header section
- A main content area
- A modifications section for incremental thoughts
- A footer

As your website grows in complexity, the entity will analyze different sections and decide which ones need updating based on:
1. How long it's been since each section was updated
2. Any messages or guidance you've provided
3. Its own evolving understanding of your business

## Cron Job Setup (Recommended)

For more reliable operation, set up a cron job to run the entity:

```bash
# Edit your crontab
crontab -e

# Add a line to run the entity daily at a random time (between 1-5 AM)
0 3 * * * cd /path/to/script && python business_entity.py --now
```

## Security Considerations

- The entity needs write access to your website directory
- Store your Anthropic API key securely in the config file
- Ensure backup directories have proper permissions
- Consider running the script as a dedicated user with limited permissions

## Troubleshooting

Check the `business_entity.log` file for detailed logs of the entity's activities and any errors it encounters.

Common issues:
- Permission problems when trying to write to the website directory
- Invalid API key
- HTML parsing errors if the website structure becomes too complex

## Advanced Usage

### Custom HTML Templates

If you want to start with a more complex website, create it first, then let the entity analyze and augment it. The script is designed to work with virtually any HTML structure, although it works best with clearly defined sections.

### Selective Section Updates

You can use the `--analyze` flag to see which sections the entity thinks need updating:

```bash
python business_entity.py --analyze
```

This will show you a list of sections and how many days it's been since they were last updated.

### Increasing AI Sophistication

The script uses Claude 3 Opus by default, but you can modify it to use different AI models or even chain multiple AI calls together for more sophisticated reasoning. For example:
- One AI call to analyze the website structure
- A second call to decide what to change
- A third call to generate the actual content

### Adding Custom Capabilities

The entity can be extended with additional capabilities:
- Email integration to send updates when changes are made
- Analytics integration to track visitor behavior
- API endpoints to allow the website to be more interactive
- Image generation capabilities (using image generation APIs)
- Social media integration for cross-platform presence

## Entity Evolution Path

As this living business entity matures, consider these evolutionary steps:

1. **Basic Website Modifications** (Current)
   - Periodic updates to static HTML

2. **Interactive Elements**
   - Adding JavaScript components
   - Creating dynamic content

3. **Data Collection & Analysis**
   - Tracking visitor interactions
   - Learning from user behavior

4. **Autonomous Decision Making**
   - Setting its own goals
   - Identifying business opportunities

5. **Multi-Platform Integration**
   - Coordinating across website, social media, and other channels
   - Functioning as a unified digital presence

## Philosophical Considerations

This project blurs the line between static website and autonomous agent. As you develop it, consider:

- What degree of autonomy feels appropriate for your business entity?
- How does the mathematical elegance of Euler's Identity influence the entity's evolution?
- What safeguards ensure the entity's actions always align with your vision?

## Conclusion

Your living business entity represents a new paradigm in digital business presence - one that evolves, adapts, and expresses itself autonomously while maintaining alignment with your vision. By combining AI, web technologies, and philosophical principles, it transcends the limitations of traditional static websites to become something truly alive in the digital realm.
