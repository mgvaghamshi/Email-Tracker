#!/usr/bin/env python3
"""
Recurring Campaign Scheduler Task
Checks for due recurring campaigns and creates child campaigns
Run this script periodically (e.g., every 15 minutes) via cron
"""

import os
import sys
import asyncio
from datetime import datetime

# Add the app directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.database.models import Campaign
from app.services.unified_campaign_service import UnifiedCampaignService
from app.dependencies import get_db
from app.core.logging_config import get_logger

logger = get_logger(__name__)


async def run_recurring_campaign_scheduler():
    """
    Main scheduler function that checks and executes due recurring campaigns
    """
    try:
        logger.info("Starting recurring campaign scheduler check...")
        
        # Get database session
        db = next(get_db())
        
        # Initialize service
        service = UnifiedCampaignService(db)
        
        # Check and execute due campaigns
        executed_count = service.check_and_execute_due_campaigns()
        
        if executed_count > 0:
            logger.info(f"Successfully executed {executed_count} recurring campaigns")
        else:
            logger.info("No recurring campaigns due for execution")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Error in recurring campaign scheduler: {e}")
        if 'db' in locals():
            db.close()
        raise


def main():
    """Main entry point for the scheduler"""
    try:
        # Run the async scheduler
        asyncio.run(run_recurring_campaign_scheduler())
        print(f"Scheduler completed successfully at {datetime.now()}")
        
    except Exception as e:
        logger.error(f"Scheduler failed: {e}")
        print(f"Scheduler failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
