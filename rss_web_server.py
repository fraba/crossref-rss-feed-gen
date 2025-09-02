#!/usr/bin/env python3
"""
Simple RSS Web Server - Serve Crossref RSS feeds via HTTP
"""

import os
import json
import logging
from datetime import datetime, timedelta
from flask import Flask, Response, request, jsonify, render_template_string
from crossref_rss_generator import CrossrefRSSGenerator

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global generator instance
rss_generator = None

def init_generator():
    """Initialize the RSS generator"""
    global rss_generator
    
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    email = os.getenv('MW_ADMIN_EMAIL')
    if not email:
        raise Exception("MW_ADMIN_EMAIL environment variable required")
    
    rss_generator = CrossrefRSSGenerator(email)
    logger.info("RSS generator initialized")

@app.route('/')
def index():
    """Simple web interface listing available feeds"""
    
    try:
        # Load journal configuration
        journals_config = rss_generator.load_journal_config()
        
        html_template = """
        <!DOCTYPE html>
        <html>
        <head>
            <title>Academic RSS Feeds</title>
            <style>
                body { font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; }
                .journal { margin: 20px 0; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
                .feed-link { color: #0066cc; text-decoration: none; font-weight: bold; }
                .feed-link:hover { text-decoration: underline; }
                .rss-icon { color: #ff6600; margin-right: 5px; }
                .description { color: #666; margin: 5px 0; }
                .meta { font-size: 0.9em; color: #888; }
            </style>
        </head>
        <body>
            <h1>📡 Academic RSS Feeds</h1>
            <p>Real-time RSS feeds from academic journals via Crossref API</p>
            
            <h2>🌟 Combined Feed</h2>
            <div class="journal">
                <a href="/rss/combined" class="feed-link">
                    <span class="rss-icon">📡</span>Combined Feed - All Journals
                </a>
                <div class="description">Latest articles from all followed journals</div>
                <div class="meta">Updates: Latest {{ days_back }} days</div>
            </div>
            
            <h2>📚 Individual Journal Feeds</h2>
            {% for journal in journals %}
            <div class="journal">
                <a href="/rss/journal/{{ journal.issn or journal.name|lower|replace(' ', '_') }}" class="feed-link">
                    <span class="rss-icon">📡</span>{{ journal.name }}
                </a>
                <div class="description">{{ journal.feed_description or 'Latest articles from ' + journal.name }}</div>
                <div class="meta">
                    ISSN: {{ journal.issn or 'Not specified' }} | 
                    Direct link: <a href="/rss/journal/{{ journal.issn or journal.name|lower|replace(' ', '_') }}">/rss/journal/{{ journal.issn or journal.name|lower|replace(' ', '_') }}</a>
                </div>
            </div>
            {% endfor %}
            
            <h2>🔧 API Endpoints</h2>
            <ul>
                <li><code>/rss/combined</code> - Combined feed from all journals</li>
                <li><code>/rss/journal/&lt;issn_or_name&gt;</code> - Individual journal feed</li>
                <li><code>/api/journals</code> - List configured journals (JSON)</li>
                <li><code>/api/status</code> - Service status (JSON)</li>
            </ul>
            
            <h2>⚙️ Parameters</h2>
            <p>Add query parameters to customize feeds:</p>
            <ul>
                <li><code>?days=14</code> - Look back 14 days (default: 7)</li>
                <li><code>?max=50</code> - Maximum articles (default: 20)</li>
                <li>Example: <a href="/rss/combined?days=14&max=30">/rss/combined?days=14&max=30</a></li>
            </ul>
            
            <div style="margin-top: 40px; padding: 15px; background: #f5f5f5; border-radius: 5px;">
                <strong>📱 How to use:</strong>
                <ol>
                    <li>Copy any RSS feed URL above</li>
                    <li>Add it to your RSS reader (Feedly, Inoreader, etc.)</li>
                    <li>Get real-time updates when new articles are published!</li>
                </ol>
            </div>
        </body>
        </html>
        """
        
        from jinja2 import Template
        template = Template(html_template)
        return template.render(journals=journals_config, days_back=7)
        
    except Exception as e:
        logger.error(f"Error loading index page: {e}")
        return f"Error: {e}", 500

@app.route('/rss/combined')
def combined_feed():
    """Serve combined RSS feed from all journals"""
    try:
        # Get parameters
        days_back = int(request.args.get('days', 7))
        max_articles_per_journal = int(request.args.get('max', 20)) // 4  # Divide among journals
        
        # Load journal configuration
        journals_config = rss_generator.load_journal_config()
        
        # Generate combined feed
        rss_content = rss_generator.generate_combined_feed(
            journals_config,
            days_back=days_back,
            max_articles_per_journal=max(1, max_articles_per_journal)
        )
        
        return Response(rss_content, mimetype='application/rss+xml')
        
    except Exception as e:
        logger.error(f"Error generating combined RSS feed: {e}")
        return f"Error generating RSS feed: {e}", 500

@app.route('/rss/journal/<identifier>')
def journal_feed(identifier):
    """Serve RSS feed for a specific journal"""
    try:
        # Get parameters
        days_back = int(request.args.get('days', 7))
        max_articles = int(request.args.get('max', 20))
        
        # Load journal configuration
        journals_config = rss_generator.load_journal_config()
        
        # Find journal by ISSN or name
        journal_config = None
        for config in journals_config:
            if (config.get('issn') == identifier or 
                config.get('name', '').lower().replace(' ', '_').replace('&', 'and') == identifier.lower()):
                journal_config = config
                break
        
        if not journal_config:
            return f"Journal not found: {identifier}", 404
        
        # Generate feed for specific journal
        rss_content = rss_generator.generate_journal_feed(
            journal_config,
            days_back=days_back,
            max_articles=max_articles
        )
        
        return Response(rss_content, mimetype='application/rss+xml')
        
    except Exception as e:
        logger.error(f"Error generating journal RSS feed for {identifier}: {e}")
        return f"Error generating RSS feed: {e}", 500

@app.route('/api/journals')
def api_journals():
    """API endpoint to list configured journals"""
    try:
        journals_config = rss_generator.load_journal_config()
        return jsonify({
            'journals': journals_config,
            'count': len(journals_config),
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        logger.error(f"Error in journals API: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/status')
def api_status():
    """API endpoint for service status"""
    try:
        # Test Crossref connection
        test_articles = rss_generator.crossref_client.get_recent_articles_by_issn(
            "0028-0836", days_back=1, limit=1
        )
        
        return jsonify({
            'status': 'healthy',
            'crossref_connection': 'ok' if test_articles else 'issues',
            'timestamp': datetime.now().isoformat(),
            'test_result': f"Found {len(test_articles)} recent articles"
        })
    except Exception as e:
        logger.error(f"Error in status API: {e}")
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/api/refresh/<identifier>')
def api_refresh_journal(identifier):
    """Force refresh of a journal feed"""
    try:
        # This would be where you could implement cache invalidation
        # For now, just return success since feeds are generated on-demand
        return jsonify({
            'message': f'Feed refresh requested for {identifier}',
            'note': 'Feeds are generated on-demand, so next request will fetch latest data',
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def create_default_journals_config():
    """Create default journal configuration if none exists"""
    default_config = [
        {
            "name": "Nature",
            "issn": "0028-0836",
            "feed_title": "Nature - Latest Research", 
            "feed_description": "Latest research articles from Nature"
        },
        {
            "name": "Science",
            "issn": "0036-8075",
            "feed_title": "Science - Latest Articles",
            "feed_description": "Latest articles from Science magazine"
        }
    ]
    
    with open('rss_journals.json', 'w') as f:
        json.dump(default_config, f, indent=2)
    
    logger.info("Created default journal configuration")
    return default_config

def main():
    """Main function to run the web server"""
    try:
        # Initialize
        init_generator()
        
        # Create default config if needed
        if not os.path.exists('rss_journals.json'):
            create_default_journals_config()
        
        # Get port from environment or default
        port = int(os.getenv('RSS_PORT', 5000))
        host = os.getenv('RSS_HOST', '127.0.0.1')
        debug = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
        
        print(f"🚀 Starting RSS Feed Server")
        print(f"📡 Serving at: http://{host}:{port}")
        print(f"🔧 Debug mode: {debug}")
        print()
        print("📋 Available endpoints:")
        print(f"   • http://{host}:{port}/ - Web interface")
        print(f"   • http://{host}:{port}/rss/combined - Combined RSS feed")
        print(f"   • http://{host}:{port}/rss/journal/<issn> - Journal-specific feed")
        print(f"   • http://{host}:{port}/api/status - Service status")
        print()
        
        app.run(host=host, port=port, debug=debug)
        
    except KeyboardInterrupt:
        print("\n👋 Server stopped by user")
    except Exception as e:
        logger.error(f"Server startup failed: {e}")
        raise

if __name__ == "__main__":
    main()