"""
Rules management module for the Pokemon Cable Club Server.
Handles loading and monitoring of rule files.
"""

import os
import logging


def find_changed_files(directory, old_files_hash):
    """
    Check if any files in the directory have changed since last check.
    
    Args:
        directory: Directory path to check
        old_files_hash: Dictionary of filename -> modification time from previous check
    
    Returns:
        tuple: (changed: bool, new_files_hash: dict)
    """
    if os.path.isdir(directory):
        new_files_hash = dict([(f, os.stat(os.path.join(directory, f)).st_mtime) 
                              for f in os.listdir(directory)])
        changed = old_files_hash.keys() != new_files_hash.keys()
        if not changed:
            for k in (old_files_hash.keys() & new_files_hash.keys()):
                if old_files_hash[k] != new_files_hash[k]:
                    changed = True
                    break
        if changed:
            logging.info('Refreshing Rules due to changes')
            return True, new_files_hash
    return False, old_files_hash


def load_rules_files(directory, files_hash):
    """
    Load all rule files from the specified directory.
    
    Args:
        directory: Directory containing rule files
        files_hash: Dictionary of files to load
    
    Returns:
        list: List of rules, where each rule is a list of strings
    """
    rules = []
    for f in iter(files_hash):
        rule = []
        with open(os.path.join(directory, f)) as rule_file:
            for num, line in enumerate(rule_file):
                line = line.strip()
                if num == 3:
                    rule.extend(line.split(','))
                else:
                    rule.append(line)
        rules.append(rule)
    return rules