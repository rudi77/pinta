#!/usr/bin/env python3
"""
Script to fix all API endpoint paths in test files
"""

import os
import re

def update_file_endpoints(file_path):
    """Update API endpoint paths in a test file"""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Store original content to check if changes were made
    original_content = content
    
    # API endpoint replacements
    replacements = [
        # Auth endpoints
        (r'"/auth/', '"/api/v1/auth/'),
        
        # Quotes endpoints  
        (r'"/quotes/', '"/api/v1/quotes/'),
        
        # Users endpoints
        (r'"/users/', '"/api/v1/users/'),
        
        # AI endpoints
        (r'"/ai/', '"/api/v1/ai/'),
        
        # Documents endpoints
        (r'"/documents/', '"/api/v1/documents/'),
        
        # Quota endpoints
        (r'"/quota/', '"/api/v1/quota/'),
    ]
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Write back if changes were made
    if content != original_content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {file_path}")
    else:
        print(f"No changes needed: {file_path}")

def main():
    """Update all test files"""
    test_dir = "tests"
    
    for filename in os.listdir(test_dir):
        if filename.endswith("_integration.py"):
            file_path = os.path.join(test_dir, filename)
            update_file_endpoints(file_path)

if __name__ == "__main__":
    main()