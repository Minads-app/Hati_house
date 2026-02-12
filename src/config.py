import os
import streamlit as st

class AppConfig:
    # Resort Info
    # Load from environment variables (set by .env or cloud secrets)
    RESORT_NAME = os.getenv("RESORT_NAME", "HATI House")
    Page_Title = os.getenv("PAGE_TITLE", f"QUẢN LÝ {RESORT_NAME}")
    Page_Icon = os.getenv("PAGE_ICON", "🏨")
    
    # Firebase
    # Default to a generic name slightly different from specific "bamboo" to avoid confusion, 
    # but keep backward compatibility if file exists in config/
    FIREBASE_KEY_PATH = os.getenv("FIREBASE_KEY_PATH", "config/firebase_key.json")
    
    # Paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    ROOT_DIR = os.path.dirname(BASE_DIR)
    CONFIG_DIR = os.path.join(ROOT_DIR, "config")
    
    # Logo
    LOGO_PATH = os.path.join(CONFIG_DIR, "logo.png")

    @staticmethod
    def get_firebase_key_path():
        """
        Returns absolute path to firebase key based on priority:
        1. Environment Variable FIREBASE_KEY_PATH
        2. 'config/firebase_key.json' (Standard deployment)
        3. 'firebase_key.json' (Legacy/Dev root)
        """
        # Check config dir first
        config_path = os.path.join(AppConfig.ROOT_DIR, "config", "firebase_key.json")
        if os.path.exists(config_path):
            return config_path
            
        # Check root dir (Legacy)
        root_path = os.path.join(AppConfig.ROOT_DIR, "firebase_key.json")
        if os.path.exists(root_path):
            return root_path
            
        return config_path # Default to config path even if missing
