#!/usr/bin/env python3
"""
Script för att lägga till Göteborgs tingsrätt feed i Scout.
Kan köras manuellt om feeden saknas i databasen.
"""
import sys
from pathlib import Path

# Lägg till apps/api i path för att importera modeller
sys.path.insert(0, str(Path(__file__).parent.parent / "apps" / "api"))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from models import ScoutFeed, Base
import os

# Database URL (använd samma som i main.py)
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql://arbetsytan:arbetsytan@localhost:5432/arbetsytan"
)

def add_domstol_feed():
    """Lägg till Göteborgs tingsrätt feed om den saknas."""
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    
    db = SessionLocal()
    
    try:
        # Kontrollera om feeden redan finns
        existing = db.query(ScoutFeed).filter(
            ScoutFeed.url == "https://www.domstol.se/feed/56/?searchPageId=1139&scope=news"
        ).first()
        
        if existing:
            print(f"Feeden 'Göteborgs tingsrätt' finns redan (ID: {existing.id})")
            if not existing.is_enabled:
                existing.is_enabled = True
                db.commit()
                print("Feeden har aktiverats.")
            return
        
        # Skapa ny feed
        feed = ScoutFeed(
            name="Göteborgs tingsrätt",
            url="https://www.domstol.se/feed/56/?searchPageId=1139&scope=news",
            is_enabled=True
        )
        db.add(feed)
        db.commit()
        db.refresh(feed)
        print(f"Feeden 'Göteborgs tingsrätt' har lagts till (ID: {feed.id})")
        
    except Exception as e:
        print(f"Fel: {e}", file=sys.stderr)
        db.rollback()
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    add_domstol_feed()
