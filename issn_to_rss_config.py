#!/usr/bin/env python3
"""
ISSN to RSS Configuration Generator
Reads a list of ISSNs and generates rss_journals.json using Crossref API
"""

import json
import requests
import time
import os
import sys
from typing import List, Dict, Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ISSNToRSSConfigGenerator:
    """Generate RSS journal configuration from ISSN list using Crossref API"""
    
    def __init__(self, email: str):
        self.email = email
        self.base_url = "https://api.crossref.org"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': f'RSSConfigGenerator/1.0 (mailto:{email})'
        })
        
    def read_issn_list(self, filename: str) -> List[str]:
        """Read ISSN list from text file"""
        issns = []
        
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Basic ISSN format validation
                    if self.validate_issn_format(line):
                        issns.append(line)
                        logger.debug(f"Added ISSN: {line}")
                    else:
                        logger.warning(f"Line {line_num}: Invalid ISSN format: {line}")
            
            logger.info(f"Read {len(issns)} valid ISSNs from {filename}")
            return issns
            
        except FileNotFoundError:
            logger.error(f"File not found: {filename}")
            raise
        except Exception as e:
            logger.error(f"Error reading {filename}: {e}")
            raise
    
    def validate_issn_format(self, issn: str) -> bool:
        """Validate ISSN format (XXXX-XXXX)"""
        import re
        pattern = r'^\d{4}-\d{3}[\dX]$'
        return bool(re.match(pattern, issn.strip()))
    
    def get_journal_info_from_crossref(self, issn: str) -> Optional[Dict]:
        """Fetch journal information from Crossref API"""
        try:
            url = f"{self.base_url}/journals/{issn}"
            params = {'mailto': self.email}
            
            logger.info(f"Fetching info for ISSN: {issn}")
            
            response = self.session.get(url, params=params, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            
            if data.get('status') != 'ok':
                logger.warning(f"Crossref returned non-ok status for ISSN {issn}: {data.get('status')}")
                return None
            
            journal_data = data.get('message', {})
            
            # Extract journal information
            journal_info = {
                'issn': issn,
                'crossref_data': journal_data
            }
            
            # Get journal title(s)
            titles = journal_data.get('title', [])
            if titles:
                journal_info['title'] = titles[0] if isinstance(titles, list) else str(titles)
            else:
                logger.warning(f"No title found for ISSN {issn}")
                journal_info['title'] = f"Journal {issn}"
            
            # Get publisher
            publisher = journal_data.get('publisher')
            if publisher:
                journal_info['publisher'] = publisher
            
            # Get additional ISSNs
            all_issns = journal_data.get('ISSN', [])
            if all_issns and len(all_issns) > 1:
                journal_info['all_issns'] = all_issns
            
            # Get subjects
            subjects = journal_data.get('subject', [])
            if subjects:
                journal_info['subjects'] = subjects
            
            logger.info(f"✅ Found: {journal_info['title']}")
            return journal_info
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request error for ISSN {issn}: {e}")
            return None
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error for ISSN {issn}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error for ISSN {issn}: {e}")
            return None
    
    def create_rss_config_entry(self, journal_info: Dict) -> Dict:
        """Create RSS configuration entry from journal info"""
        issn = journal_info['issn']
        title = journal_info.get('title', f'Journal {issn}')
        
        # Clean up title
        title_clean = title.strip()
        if not title_clean:
            title_clean = f'Journal {issn}'
        
        # Create RSS feed title and description
        feed_title = f"{title_clean} - Latest Articles"
        feed_description = f"Latest research articles from {title_clean}"
        
        # Add publisher info if available
        publisher = journal_info.get('publisher')
        if publisher:
            feed_description += f" (Published by {publisher})"
        
        # Create configuration entry
        config_entry = {
            "name": title_clean,
            "issn": issn,
            "feed_title": feed_title,
            "feed_description": feed_description
        }
        
        # Add optional fields
        if publisher:
            config_entry["publisher"] = publisher
        
        subjects = journal_info.get('subjects', [])
        if subjects:
            config_entry["subjects"] = subjects[:5]  # Limit to 5 subjects
        
        all_issns = journal_info.get('all_issns', [])
        if all_issns and len(all_issns) > 1:
            config_entry["all_issns"] = all_issns
        
        return config_entry
    
    def generate_config(self, issn_file: str, output_file: str = 'rss_journals.json', 
                       rate_limit_delay: float = 1.0) -> List[Dict]:
        """Generate complete RSS configuration from ISSN list"""
        
        logger.info(f"🚀 Starting RSS configuration generation")
        logger.info(f"📄 Input file: {issn_file}")
        logger.info(f"📄 Output file: {output_file}")
        
        # Read ISSNs
        issns = self.read_issn_list(issn_file)
        
        if not issns:
            logger.error("No valid ISSNs found in input file")
            return []
        
        # Generate configuration entries
        config_entries = []
        failed_issns = []
        
        for i, issn in enumerate(issns, 1):
            logger.info(f"Processing {i}/{len(issns)}: {issn}")
            
            # Get journal info from Crossref
            journal_info = self.get_journal_info_from_crossref(issn)
            
            if journal_info:
                # Create RSS config entry
                config_entry = self.create_rss_config_entry(journal_info)
                config_entries.append(config_entry)
                
                logger.info(f"✅ Added: {config_entry['name']}")
            else:
                # Create fallback entry for failed lookups
                failed_issns.append(issn)
                fallback_entry = {
                    "name": f"Journal {issn}",
                    "issn": issn,
                    "feed_title": f"Journal {issn} - Latest Articles",
                    "feed_description": f"Latest articles from journal with ISSN {issn}",
                    "_note": "Journal name lookup failed - please update manually"
                }
                config_entries.append(fallback_entry)
                logger.warning(f"⚠️ Added fallback entry for: {issn}")
            
            # Rate limiting - be nice to Crossref
            if i < len(issns):  # Don't delay after the last request
                time.sleep(rate_limit_delay)
        
        # Save configuration
        try:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(config_entries, f, indent=2, ensure_ascii=False)
            
            logger.info(f"✅ Saved RSS configuration to: {output_file}")
            
        except Exception as e:
            logger.error(f"Error saving configuration: {e}")
            raise
        
        # Print summary
        self.print_summary(config_entries, failed_issns, output_file)
        
        return config_entries
    
    def print_summary(self, config_entries: List[Dict], failed_issns: List[str], output_file: str):
        """Print generation summary"""
        logger.info("\n" + "="*60)
        logger.info("RSS CONFIGURATION GENERATION SUMMARY")
        logger.info("="*60)
        
        logger.info(f"📊 Total journals processed: {len(config_entries)}")
        logger.info(f"✅ Successful lookups: {len(config_entries) - len(failed_issns)}")
        logger.info(f"⚠️ Failed lookups: {len(failed_issns)}")
        logger.info(f"📄 Output file: {output_file}")
        
        if failed_issns:
            logger.info(f"\n⚠️ Failed ISSNs (please check manually):")
            for issn in failed_issns:
                logger.info(f"   • {issn}")
        
        logger.info(f"\n📡 Sample RSS URLs:")
        logger.info(f"   • Combined: http://localhost:5000/rss/combined")
        for entry in config_entries[:3]:  # Show first 3
            issn = entry['issn']
            name = entry['name']
            logger.info(f"   • {name}: http://localhost:5000/rss/journal/{issn}")
        
        if len(config_entries) > 3:
            logger.info(f"   • ... and {len(config_entries) - 3} more")
        
        logger.info(f"\n🎉 Configuration generation completed!")
        logger.info(f"Next step: Run 'python rss_web_server.py' to start serving RSS feeds")
    
    def validate_generated_config(self, config_file: str) -> bool:
        """Validate the generated configuration file"""
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            if not isinstance(config_data, list):
                logger.error("Configuration should be a list of journal entries")
                return False
            
            required_fields = ['name', 'issn', 'feed_title', 'feed_description']
            
            for i, entry in enumerate(config_data):
                for field in required_fields:
                    if field not in entry:
                        logger.error(f"Entry {i}: Missing required field '{field}'")
                        return False
                
                # Validate ISSN format
                if not self.validate_issn_format(entry['issn']):
                    logger.error(f"Entry {i}: Invalid ISSN format: {entry['issn']}")
                    return False
            
            logger.info(f"✅ Configuration validation passed: {len(config_data)} entries")
            return True
            
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            return False


def create_sample_issn_file():
    """Create a sample ISSN list file for testing"""
    sample_issns = [
        "# Sample ISSN list for RSS feed generation",
        "# One ISSN per line, comments start with #",
        "",
        "# Nature journals",
        "0028-0836",  # Nature
        "1476-4687",  # Nature Biotechnology
        "",
        "# Science journals", 
        "0036-8075",  # Science
        "1095-9203",  # Science (online)
        "",
        "# Medical journals",
        "0140-6736",  # The Lancet
        "0028-4793",  # New England Journal of Medicine
    ]
    
    with open('sample_issn_list.txt', 'w') as f:
        f.write('\n'.join(sample_issns))
    
    print("Created sample_issn_list.txt for testing")


def main():
    """Main function with command line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate RSS journal configuration from ISSN list")
    parser.add_argument('input_file', nargs='?', default='issn_list.txt', 
                       help='Input file with ISSNs (default: issn_list.txt)')
    parser.add_argument('--output', '-o', default='rss_journals.json',
                       help='Output configuration file (default: rss_journals.json)')
    parser.add_argument('--email', '-e', help='Email for Crossref API (required)')
    parser.add_argument('--delay', '-d', type=float, default=1.0,
                       help='Delay between requests in seconds (default: 1.0)')
    parser.add_argument('--validate', action='store_true',
                       help='Validate existing configuration file')
    parser.add_argument('--create-sample', action='store_true',
                       help='Create sample ISSN list file')
    
    args = parser.parse_args()
    
    # Handle special modes
    if args.create_sample:
        create_sample_issn_file()
        return
    
    # Get email from arguments or environment
    email = args.email or os.getenv('MW_ADMIN_EMAIL') or os.getenv('EMAIL')
    
    if not email:
        print("❌ Email required for Crossref API")
        print("Provide via:")
        print("  --email your-email@domain.com")
        print("  or set MW_ADMIN_EMAIL environment variable")
        print("  or set EMAIL environment variable")
        return
    
    # Initialize generator
    generator = ISSNToRSSConfigGenerator(email)
    
    # Validate mode
    if args.validate:
        if os.path.exists(args.output):
            is_valid = generator.validate_generated_config(args.output)
            print("✅ Configuration is valid" if is_valid else "❌ Configuration has errors")
        else:
            print(f"❌ Configuration file not found: {args.output}")
        return
    
    # Check input file exists
    if not os.path.exists(args.input_file):
        print(f"❌ Input file not found: {args.input_file}")
        print("Create it with ISSNs like:")
        print("  0028-0836")
        print("  0036-8075")
        print("  # comments start with #")
        print()
        print("Or run with --create-sample to create a sample file")
        return
    
    try:
        # Generate configuration
        config_entries = generator.generate_config(
            args.input_file, 
            args.output, 
            rate_limit_delay=args.delay
        )
        
        # Validate the generated config
        if config_entries:
            generator.validate_generated_config(args.output)
        
    except KeyboardInterrupt:
        print("\n👋 Generation cancelled by user")
    except Exception as e:
        logger.error(f"Generation failed: {e}")
        raise


def quick_test():
    """Quick test function"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    
    email = os.getenv('MW_ADMIN_EMAIL') or os.getenv('EMAIL')
    if not email:
        print("❌ Email required. Set MW_ADMIN_EMAIL or EMAIL environment variable")
        return
    
    # Test with a few well-known ISSNs
    test_issns = ["0028-0836", "0036-8075", "0140-6736"]  # Nature, Science, Lancet
    
    # Create test file
    with open('test_issn_list.txt', 'w') as f:
        f.write("# Test ISSN list\n")
        for issn in test_issns:
            f.write(f"{issn}\n")
    
    print(f"🧪 Testing with {len(test_issns)} journals...")
    
    generator = ISSNToRSSConfigGenerator(email)
    config_entries = generator.generate_config('test_issn_list.txt', 'test_rss_journals.json')
    
    if config_entries:
        print("\n✅ Test completed successfully!")
        print("Generated: test_rss_journals.json")
        
        # Show first entry
        print("\nSample entry:")
        print(json.dumps(config_entries[0], indent=2))
    else:
        print("❌ Test failed")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # Interactive mode
        print("📡 ISSN to RSS Configuration Generator")
        print("=" * 50)
        print("1. Generate from issn_list.txt")
        print("2. Run quick test")
        print("3. Create sample ISSN file")
        print("4. Validate existing config")
        print()
        
        choice = input("Choose option (1-4): ").strip()
        
        if choice == '1':
            main()
        elif choice == '2':
            quick_test()
        elif choice == '3':
            create_sample_issn_file()
        elif choice == '4':
            email = os.getenv('MW_ADMIN_EMAIL') or os.getenv('EMAIL')
            if email:
                generator = ISSNToRSSConfigGenerator(email)
                generator.validate_generated_config('rss_journals.json')
            else:
                print("❌ Email required (set MW_ADMIN_EMAIL environment variable)")
        else:
            print("Invalid choice")
    else:
        main()