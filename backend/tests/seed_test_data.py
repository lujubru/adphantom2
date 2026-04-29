"""
Seed script for testing unified messages and ad-preview features.
Creates test data directly in MongoDB for testing purposes.
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone
import uuid

MONGO_URL = "mongodb://localhost:27017"
DB_NAME = "traffic_guardian"


async def seed_test_data():
    """Seed test data for unified messages and ad-preview testing"""
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    
    print("Seeding test data...")
    
    # Create test lines
    line1_id = f"TEST_LINE_{uuid.uuid4().hex[:8]}"
    line2_id = f"TEST_LINE_{uuid.uuid4().hex[:8]}"
    
    line1 = {
        "id": line1_id,
        "name": "TEST_Line_Unified_1",
        "phone_number_id": "TEST_PHONE_ID_1",
        "whatsapp_number": "5491100000001",
        "whatsapp_token": "TEST_TOKEN_1",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    line2 = {
        "id": line2_id,
        "name": "TEST_Line_Unified_2",
        "phone_number_id": "TEST_PHONE_ID_2",
        "whatsapp_number": "5491100000002",
        "whatsapp_token": "TEST_TOKEN_2",
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.crm_lines.insert_many([line1, line2])
    print(f"Created lines: {line1_id}, {line2_id}")
    
    # Create leads with SAME phone number but different lines (for unified messages test)
    shared_phone = "5491100000999"
    lead1_id = f"TEST_LEAD_{uuid.uuid4().hex[:8]}"
    lead2_id = f"TEST_LEAD_{uuid.uuid4().hex[:8]}"
    
    lead1 = {
        "id": lead1_id,
        "name": "TEST_Lead_Unified_1",
        "phone": shared_phone,
        "line_id": line1_id,
        "status": "nuevo",
        "source": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    lead2 = {
        "id": lead2_id,
        "name": "TEST_Lead_Unified_2",
        "phone": shared_phone,
        "line_id": line2_id,
        "status": "nuevo",
        "source": "test",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.crm_leads.insert_many([lead1, lead2])
    print(f"Created leads with shared phone {shared_phone}: {lead1_id}, {lead2_id}")
    
    # Create messages for both leads
    msg1_id = f"TEST_MSG_{uuid.uuid4().hex[:8]}"
    msg2_id = f"TEST_MSG_{uuid.uuid4().hex[:8]}"
    msg3_id = f"TEST_MSG_{uuid.uuid4().hex[:8]}"
    
    messages = [
        {
            "id": msg1_id,
            "lead_id": lead1_id,
            "content": "Hola, mensaje 1 del lead 1",
            "sender": "lead",
            "message_type": "text",
            "created_at": "2025-01-01T10:00:00Z",
        },
        {
            "id": msg2_id,
            "lead_id": lead1_id,
            "content": "Respuesta del admin al lead 1",
            "sender": "admin",
            "message_type": "text",
            "created_at": "2025-01-01T10:01:00Z",
        },
        {
            "id": msg3_id,
            "lead_id": lead2_id,
            "content": "Mensaje del lead 2 (mismo teléfono)",
            "sender": "lead",
            "message_type": "text",
            "created_at": "2025-01-01T10:02:00Z",
        },
    ]
    
    await db.crm_messages.insert_many(messages)
    print(f"Created messages: {msg1_id}, {msg2_id}, {msg3_id}")
    
    # Create leads for ad-preview testing
    # Lead with referral.source_id but NO source_url
    lead_ad1_id = f"TEST_LEAD_AD_{uuid.uuid4().hex[:8]}"
    lead_ad1 = {
        "id": lead_ad1_id,
        "name": "TEST_Lead_AdPreview_SourceIdOnly",
        "phone": "5491100000777",
        "line_id": line1_id,
        "status": "nuevo",
        "source": "meta_ad",
        "referral": {
            "source_id": "123456789012345",
            "headline": "Test Ad Headline",
            "body": "Test ad body text",
            # NO source_url - should fallback to ads_library_url
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Lead with BOTH referral.source_url and referral.source_id
    lead_ad2_id = f"TEST_LEAD_AD_{uuid.uuid4().hex[:8]}"
    lead_ad2 = {
        "id": lead_ad2_id,
        "name": "TEST_Lead_AdPreview_BothUrls",
        "phone": "5491100000666",
        "line_id": line1_id,
        "status": "nuevo",
        "source": "meta_ad",
        "referral": {
            "source_id": "987654321098765",
            "source_url": "https://www.facebook.com/some-page/posts/12345",
            "headline": "Test Ad with Both URLs",
            "body": "Test ad body",
        },
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    # Lead with NO referral (for regression test)
    lead_ad3_id = f"TEST_LEAD_AD_{uuid.uuid4().hex[:8]}"
    lead_ad3 = {
        "id": lead_ad3_id,
        "name": "TEST_Lead_NoReferral",
        "phone": "5491100000555",
        "line_id": line1_id,
        "status": "nuevo",
        "source": "manual",
        # NO referral, landing_code, ad_source, utm_content, ctwa_clid
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    
    await db.crm_leads.insert_many([lead_ad1, lead_ad2, lead_ad3])
    print(f"Created ad-preview test leads: {lead_ad1_id}, {lead_ad2_id}, {lead_ad3_id}")
    
    # Return IDs for test reference
    return {
        "line_ids": [line1_id, line2_id],
        "unified_lead_ids": [lead1_id, lead2_id],
        "unified_phone": shared_phone,
        "message_ids": [msg1_id, msg2_id, msg3_id],
        "ad_preview_lead_ids": {
            "source_id_only": lead_ad1_id,
            "both_urls": lead_ad2_id,
            "no_referral": lead_ad3_id,
        }
    }


async def cleanup_test_data():
    """Clean up all TEST_ prefixed data"""
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=5000)
    db = client[DB_NAME]
    
    print("Cleaning up test data...")
    
    # Delete test messages
    result = await db.crm_messages.delete_many({"id": {"$regex": "^TEST_"}})
    print(f"Deleted {result.deleted_count} test messages")
    
    # Delete test leads
    result = await db.crm_leads.delete_many({"id": {"$regex": "^TEST_"}})
    print(f"Deleted {result.deleted_count} test leads")
    
    # Delete test lines
    result = await db.crm_lines.delete_many({"id": {"$regex": "^TEST_"}})
    print(f"Deleted {result.deleted_count} test lines")


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup_test_data())
    else:
        result = asyncio.run(seed_test_data())
        print("\nSeeded data IDs:")
        print(result)
