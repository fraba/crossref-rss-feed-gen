#!/usr/bin/env python3
"""
Fixed Enhanced Minimal RSS Generator - Proper UTF-8 encoding support
Uses generated rss_journals.json config
No external dependencies required - only Python standard library!
"""

import json
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from xml.dom import minidom
from datetime import datetime, timedelta
import time
import os
import http.server
import socketserver
from urllib.parse import urlparse, parse_qs
import html
import re

class MinimalCrossrefClient:
    """Minimal Crossref client using only standard library"""
    
    def __init__(self, email):
        self.email = email
        self.base_url = "https://api.crossref.org"
    
    def get_recent_articles_by_issn(self, issn, days_back=7, limit=20):
        """Get recent articles by ISSN"""
        from_date = (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d')
        
        # Build URL
        params = {
            'filter': f'issn:{issn},from-pub-date:{from_date}',
            'rows': str(limit),
            'sort': 'published',
            'order': 'desc',
            'mailto': self.email
        }
        
        url = f"{self.base_url}/works?" + urllib.parse.urlencode(params)
        
        try:
            print(f"Fetching articles for ISSN: {issn}")
            
            # Create request with User-Agent
            req = urllib.request.Request(url)
            req.add_header('User-Agent', f'MinimalRSSGenerator/1.0 (mailto:{self.email})')
            
            # Make request
            with urllib.request.urlopen(req, timeout=30) as response:
                data = json.loads(response.read().decode('utf-8'))
                articles = data.get('message', {}).get('items', [])
                print(f"Found {len(articles)} articles for {issn}")
                return articles
                
        except Exception as e:
            print(f"Error fetching from {issn}: {e}")
            return []

class FixedEnhancedMinimalRSSGenerator:
    """Fixed enhanced minimal RSS generator with proper UTF-8 encoding"""
    
    def __init__(self, email, config_file='rss_journals.json'):
        self.client = MinimalCrossrefClient(email)
        self.config_file = config_file
        self.journals_config = self.load_journals_config()
    
    def load_journals_config(self):
        """Load journal configuration from JSON file"""
        try:
            with open(self.config_file, 'r', encoding='utf-8') as f:
                config = json.load(f)
            print(f"Loaded {len(config)} journals from {self.config_file}")
            return config
        except FileNotFoundError:
            print(f"⚠️  Config file {self.config_file} not found!")
            print("Run: python3 issn_to_rss_config.py issn_list.txt")
            return []
        except Exception as e:
            print(f"Error loading config: {e}")
            return []
    
    def clean_text(self, text):
        """Clean text for XML output - fix encoding and HTML entities"""
        if not text:
            return ""
        
        # Convert to string if not already
        text = str(text)
        
        # Fix HTML entities first
        text = html.unescape(text)  # Convert &amp; back to &, etc.
        
        # Remove HTML tags thoroughly
        text = re.sub(r'<[^>]+>', '', text)  # Remove HTML tags like <i>...</i>
        text = re.sub(r'&lt;[^&]*&gt;', '', text)  # Remove escaped HTML tags like &lt;i&gt;
        
        # Clean up whitespace and normalize
        text = re.sub(r'\s+', ' ', text)  # Replace multiple whitespace with single space
        text = text.strip()
        
        return text
    
    def clean_html_text(self, text):
        """Clean text for HTML display"""
        if not text:
            return ""
        
        # Unescape HTML entities and then escape for HTML output
        text = html.unescape(str(text))
        text = html.escape(text, quote=False)  # Don't escape quotes
        return text
    
    def find_journal_by_identifier(self, identifier):
        """Find journal config by ISSN or name"""
        for journal in self.journals_config:
            # Match by ISSN
            if journal.get('issn') == identifier:
                return journal
            
            # Match by name (case-insensitive, normalized)
            journal_name_normalized = journal.get('name', '').lower().replace(' ', '_').replace('&', 'and')
            if journal_name_normalized == identifier.lower():
                return journal
        
        return None
    
    def create_rss_feed(self, articles, feed_config):
        """Create RSS feed XML with proper UTF-8 encoding"""
        # Create RSS structure with namespaces
        rss = ET.Element('rss', version='2.0')
        rss.set('xmlns:atom', 'http://www.w3.org/2005/Atom')
        channel = ET.SubElement(rss, 'channel')
        
        # Channel info - clean all text
        title = ET.SubElement(channel, 'title')
        title.text = self.clean_text(feed_config.get('feed_title', 'Academic Articles'))
        
        description = ET.SubElement(channel, 'description') 
        description.text = self.clean_text(feed_config.get('feed_description', 'Latest academic articles'))
        
        link = ET.SubElement(channel, 'link')
        link.text = 'http://localhost:8000'
        
        # Add self-link for RSS validation
        atom_link = ET.SubElement(channel, '{http://www.w3.org/2005/Atom}link')
        atom_link.set('href', 'http://localhost:8000')
        atom_link.set('rel', 'self')
        atom_link.set('type', 'application/rss+xml')
        
        language = ET.SubElement(channel, 'language')
        language.text = 'en-us'
        
        last_build_date = ET.SubElement(channel, 'lastBuildDate')
        last_build_date.text = datetime.now().strftime('%a, %d %b %Y %H:%M:%S +0000')
        
        # Add journal info - clean publisher name
        publisher = feed_config.get('publisher')
        if publisher:
            managing_editor = ET.SubElement(channel, 'managingEditor')
            clean_publisher = self.clean_text(publisher)
            managing_editor.text = f"editor@example.com ({clean_publisher})"
        
        # Add articles
        for article in articles:
            self.add_article_to_feed(channel, article, feed_config)
        
        # Convert to XML with proper UTF-8 encoding
        rough_string = ET.tostring(rss, encoding='utf-8', xml_declaration=True)
        
        # Parse and prettify while preserving UTF-8
        try:
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent="  ", encoding='utf-8')
            
            # Return as UTF-8 string
            if isinstance(pretty_xml, bytes):
                return pretty_xml.decode('utf-8')
            else:
                return pretty_xml
                
        except Exception as e:
            # Fallback: return basic XML if prettifying fails
            print(f"Warning: XML prettifying failed: {e}")
            return rough_string.decode('utf-8')
    
    def add_article_to_feed(self, channel, article, feed_config):
        """Add article as RSS item with proper encoding"""
        item = ET.SubElement(channel, 'item')
        
        # Title - clean thoroughly
        title = ET.SubElement(item, 'title')
        article_title = article.get('title', ['Untitled'])
        if isinstance(article_title, list):
            article_title = article_title[0] if article_title else 'Untitled'
        
        # Clean the title properly
        clean_title = self.clean_text(article_title)
        title.text = clean_title
        
        # Link and GUID
        doi = article.get('DOI')
        if doi:
            link = ET.SubElement(item, 'link')
            link.text = f"https://doi.org/{doi}"
            
            guid = ET.SubElement(item, 'guid')
            guid.text = f"https://doi.org/{doi}"
            guid.set('isPermaLink', 'true')
        
        # Description - clean abstract or author info
        description = ET.SubElement(item, 'description')
        description_text = ""
        
        # Try abstract first
        abstract = article.get('abstract')
        if abstract:
            clean_abstract = self.clean_text(abstract)
            if clean_abstract and len(clean_abstract.strip()) > 10:
                description_text = clean_abstract[:500] + "..." if len(clean_abstract) > 500 else clean_abstract
        
        # Fallback to authors if no good abstract
        if not description_text:
            authors = article.get('author', [])
            if authors:
                author_names = []
                for author in authors[:3]:
                    name_parts = []
                    given = self.clean_text(author.get('given', ''))
                    family = self.clean_text(author.get('family', ''))
                    
                    if given:
                        name_parts.append(given)
                    if family:
                        name_parts.append(family)
                    
                    if name_parts:
                        author_names.append(' '.join(name_parts))
                
                if author_names:
                    author_text = ', '.join(author_names)
                    if len(authors) > 3:
                        author_text += ' et al.'
                    description_text = f"Authors: {author_text}"
        
        # Set description
        description.text = description_text or "No description available"
        
        # Publication date
        pub_date = article.get('published')
        if pub_date and 'date-parts' in pub_date:
            try:
                date_parts = pub_date['date-parts'][0]
                if len(date_parts) >= 3:
                    pub_datetime = datetime(date_parts[0], date_parts[1], date_parts[2])
                elif len(date_parts) >= 2:
                    pub_datetime = datetime(date_parts[0], date_parts[1], 1)
                else:
                    pub_datetime = datetime(date_parts[0], 1, 1)
                
                pub_date_elem = ET.SubElement(item, 'pubDate')
                pub_date_elem.text = pub_datetime.strftime('%a, %d %b %Y %H:%M:%S +0000')
            except:
                pass
        
        # Source (journal name) - clean it
        source = ET.SubElement(item, 'source')
        source.text = self.clean_text(feed_config.get('name', 'Unknown Journal'))
        
        # Category (subjects if available) - clean them
        subjects = feed_config.get('subjects', [])
        for subject in subjects[:3]:  # Limit to 3 categories
            if subject and subject.strip():  # Only add non-empty subjects
                category = ET.SubElement(item, 'category')
                category.text = self.clean_text(subject)
    
    def generate_journal_feed(self, journal_config, days_back=7, max_articles=20):
        """Generate RSS feed for a single journal"""
        issn = journal_config['issn']
        journal_name = journal_config['name']
        
        print(f"Generating feed for: {journal_name} ({issn})")
        
        # Get articles
        articles = self.client.get_recent_articles_by_issn(issn, days_back, max_articles)
        
        return self.create_rss_feed(articles, journal_config)
    
    def generate_combined_feed(self, days_back=7, max_articles_per_journal=5):
        """Generate combined RSS feed from all journals"""
        print("Generating combined feed from all journals...")
        
        all_articles = []
        
        for journal_config in self.journals_config:
            try:
                issn = journal_config['issn']
                articles = self.client.get_recent_articles_by_issn(
                    issn, days_back, max_articles_per_journal
                )
                
                # Add journal info to each article
                for article in articles:
                    article['_journal_info'] = journal_config
                
                all_articles.extend(articles)
                print(f"Added {len(articles)} articles from {journal_config['name']}")
                
            except Exception as e:
                print(f"Error fetching from {journal_config.get('name', 'Unknown')}: {e}")
        
        # Sort by publication date
        def get_pub_date(article):
            pub_date = article.get('published', {})
            if 'date-parts' in pub_date and pub_date['date-parts']:
                try:
                    date_parts = pub_date['date-parts'][0]
                    if len(date_parts) >= 3:
                        return datetime(date_parts[0], date_parts[1], date_parts[2])
                    elif len(date_parts) >= 2:
                        return datetime(date_parts[0], date_parts[1], 1)
                    else:
                        return datetime(date_parts[0], 1, 1)
                except:
                    pass
            return datetime.min
        
        all_articles.sort(key=get_pub_date, reverse=True)
        
        # Combined feed config
        combined_config = {
            'feed_title': 'Latest Academic Articles - Combined Feed',
            'feed_description': f'Combined feed from {len(self.journals_config)} academic journals',
            'name': 'Combined Feed'
        }
        
        print(f"Combined feed has {len(all_articles)} total articles")
        return self.create_rss_feed(all_articles, combined_config)

class FixedHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Fixed HTTP handler with proper UTF-8 support"""
    
    def __init__(self, *args, **kwargs):
        # Get email from environment
        self.email = os.environ.get('EMAIL', 'user@example.com')
        self.generator = FixedEnhancedMinimalRSSGenerator(self.email)
        super().__init__(*args, **kwargs)
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)
        
        if path == '/':
            self.serve_index()
        elif path == '/rss/combined':
            self.serve_combined_rss(query)
        elif path.startswith('/rss/journal/'):
            identifier = path.replace('/rss/journal/', '')
            self.serve_journal_rss(identifier, query)
        elif path.startswith('/rss/'):
            # Legacy endpoint
            identifier = path.replace('/rss/', '')
            self.serve_journal_rss(identifier, query)
        else:
            self.send_error(404, "RSS feed not found")
    
    def serve_index(self):
        """Serve enhanced index page with proper UTF-8 encoding"""
        journals = self.generator.journals_config
        
        # Build journal list HTML with proper encoding
        journal_links = []
        for journal in journals:
            issn = journal['issn']
            name = self.generator.clean_html_text(journal['name'])
            description = self.generator.clean_html_text(journal.get('feed_description', f'Latest articles from {name}'))
            publisher = self.generator.clean_html_text(journal.get('publisher', ''))
            
            publisher_text = f" ({publisher})" if publisher else ""
            
            journal_links.append(f"""
                <li style="margin: 10px 0;">
                    <strong><a href="/rss/journal/{issn}">{name}</a></strong>{publisher_text}<br>
                    <small style="color: #666;">{description}</small><br>
                    <code style="background: #f0f0f0; padding: 2px 4px;">ISSN: {issn}</code>
                </li>
            """)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Academic RSS Feeds</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 20px auto; padding: 20px; }}
        .header {{ background: #f8f9fa; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .feed-section {{ margin: 30px 0; }}
        .feed-link {{ color: #0066cc; text-decoration: none; font-weight: bold; }}
        .feed-link:hover {{ text-decoration: underline; }}
        .stats {{ background: #e9ecef; padding: 15px; border-radius: 5px; margin: 20px 0; }}
        ul {{ list-style-type: none; padding: 0; }}
        li {{ border-bottom: 1px solid #eee; padding: 10px 0; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📡 Academic RSS Feeds</h1>
        <p>Real-time RSS feeds from {len(journals)} academic journals via Crossref API</p>
    </div>
    
    <div class="stats">
        <strong>📊 Statistics:</strong> {len(journals)} journals configured
    </div>
    
    <div class="feed-section">
        <h2>🌟 Combined Feed</h2>
        <p><a href="/rss/combined" class="feed-link">📡 Combined Feed - All Journals</a></p>
        <small>Latest articles from all configured journals</small>
    </div>
    
    <div class="feed-section">
        <h2>📚 Individual Journal Feeds</h2>
        <ul>
            {''.join(journal_links)}
        </ul>
    </div>
    
    <div class="feed-section">
        <h2>⚙️ Parameters</h2>
        <p>Add query parameters to customize feeds:</p>
        <ul style="list-style-type: disc; margin-left: 20px;">
            <li><code>?days=14</code> - Look back 14 days (default: 7)</li>
            <li><code>?max=50</code> - Maximum articles (default: 20)</li>
            <li>Example: <a href="/rss/combined?days=14&max=30">/rss/combined?days=14&max=30</a></li>
        </ul>
    </div>
    
    <div class="feed-section">
        <h2>📱 Usage</h2>
        <ol>
            <li>Copy any RSS feed URL above</li>
            <li>Add it to your RSS reader (Feedly, Inoreader, etc.)</li>
            <li>Get real-time updates when new articles are published!</li>
        </ol>
    </div>
</body>
</html>"""
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.send_header('Cache-Control', 'no-cache')
        self.end_headers()
        
        # Ensure UTF-8 encoding for the response
        self.wfile.write(html.encode('utf-8'))
    
    def serve_combined_rss(self, query):
        """Serve combined RSS feed with proper encoding"""
        try:
            days = int(query.get('days', ['7'])[0])
            max_per_journal = int(query.get('max', ['20'])[0]) // max(1, len(self.generator.journals_config))
            max_per_journal = max(1, max_per_journal)  # At least 1 article per journal
            
            rss_content = self.generator.generate_combined_feed(days, max_per_journal)
            
            self.send_response(200)
            self.send_header('Content-type', 'application/rss+xml; charset=utf-8')
            self.send_header('Cache-Control', 'max-age=900')  # 15 minute cache
            self.end_headers()
            
            # Write UTF-8 encoded content
            self.wfile.write(rss_content.encode('utf-8'))
            
        except Exception as e:
            print(f"Error generating combined RSS: {e}")
            self.send_error(500, f"RSS Generation Error: {e}")
    
    def serve_journal_rss(self, identifier, query):
        """Serve RSS feed for specific journal with proper encoding"""
        try:
            # Find journal in config
            journal_config = self.generator.find_journal_by_identifier(identifier)
            
            if not journal_config:
                self.send_error(404, f"Journal not found: {identifier}")
                return
            
            days = int(query.get('days', ['7'])[0])
            max_articles = int(query.get('max', ['20'])[0])
            
            rss_content = self.generator.generate_journal_feed(
                journal_config, days, max_articles
            )
            
            self.send_response(200)
            self.send_header('Content-type', 'application/rss+xml; charset=utf-8')
            self.send_header('Cache-Control', 'max-age=900')  # 15 minute cache
            self.end_headers()
            
            # Write UTF-8 encoded content
            self.wfile.write(rss_content.encode('utf-8'))
            
        except Exception as e:
            print(f"Error generating journal RSS for {identifier}: {e}")
            self.send_error(500, f"RSS Generation Error: {e}")

def main():
    """Run the fixed enhanced minimal RSS server"""
    
    # Check for email
    email = os.environ.get('EMAIL')
    if not email:
        print("⚠️  EMAIL environment variable not set!")
        print("Set it like: EMAIL=your-email@domain.com python3 fixed_enhanced_minimal_rss.py")
        email = input("Enter your email for Crossref API: ").strip()
        if not email:
            print("Email required for Crossref API compliance")
            return
        os.environ['EMAIL'] = email
    
    # Check for config file
    if not os.path.exists('rss_journals.json'):
        print("⚠️  rss_journals.json not found!")
        print("Generate it first: EMAIL=your-email@domain.com python3 issn_to_rss_config.py issn_list.txt")
        return
    
    port = int(os.environ.get('PORT', 8000))
    
    print(f"🚀 Starting Fixed Enhanced RSS Server")
    print(f"📧 Using email: {email}")
    print(f"🌐 Server: http://localhost:{port}")
    print(f"📡 Features:")
    print(f"   • ✅ Proper UTF-8 encoding")
    print(f"   • ✅ HTML entity cleanup") 
    print(f"   • ✅ Special character support")
    print(f"   • ✅ Clean XML output")
    print()
    print(f"📋 RSS feeds:")
    print(f"   • http://localhost:{port}/ - Web interface")
    print(f"   • http://localhost:{port}/rss/combined - Combined feed")
    print(f"   • http://localhost:{port}/rss/journal/<issn> - Individual feeds")
    print()
    print("Press Ctrl+C to stop")
    
    try:
        with socketserver.TCPServer(("", port), FixedHTTPRequestHandler) as httpd:
            httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")

if __name__ == "__main__":
    main()