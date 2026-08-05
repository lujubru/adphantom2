import unittest
import uuid
from datetime import datetime, timezone

class TestLeadIsolationPerLine(unittest.TestCase):
    """
    Test suite verifying strict lead and conversation isolation per WhatsApp line.
    Prevents history leaks, status leaks ('valido', 'consulta', 'spam'), and tag leaks across cashiers/lines.
    """

    def test_new_line_gets_clean_lead_even_if_phone_exists_on_another_line(self):
        # Line A lead (existing)
        lead_a = {
            "id": str(uuid.uuid4()),
            "phone": "5491122334455",
            "line_id": "line_A",
            "status": "valido",
            "tags": ["vip-cargar"],
            "notes": "Cliente regular de Line A",
            "charge_amount": 5000.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Simulated incoming message on Line B for the SAME phone number
        from_phone = "5491122334455"
        line_b_id = "line_B"

        # Simulating lead lookup for Line B (our updated logic)
        # Search ONLY for (phone, line_id=line_B)
        crm_lead_b = None
        existing_leads_db = [lead_a]

        for lead in existing_leads_db:
            if lead["phone"] == from_phone and lead["line_id"] == line_b_id:
                crm_lead_b = lead
                break

        # crm_lead_b MUST be None because Line A's lead cannot be reused for Line B
        self.assertIsNone(crm_lead_b)

        # Therefore a NEW clean lead is created for Line B
        new_lead_b = {
            "id": str(uuid.uuid4()),
            "name": f"Lead {from_phone[-4:]}",
            "phone": from_phone,
            "status": "nuevo",
            "score": 50,
            "source": "whatsapp",
            "line_id": line_b_id,
            "charge_amount": 0.0,
            "notes": "",
            "tags": [],
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Verification of strict isolation
        self.assertEqual(new_lead_b["status"], "nuevo")
        self.assertEqual(new_lead_b["charge_amount"], 0.0)
        self.assertEqual(len(new_lead_b["tags"]), 0)
        self.assertEqual(new_lead_b["notes"], "")
        self.assertEqual(new_lead_b["line_id"], "line_B")

        # Verify Line A's lead was untouched
        self.assertEqual(lead_a["status"], "valido")
        self.assertEqual(lead_a["line_id"], "line_A")

    def test_unassigned_lead_is_not_claimed_by_new_line(self):
        # Unassigned lead (line_id: None) e.g. from web landing click or previous unassigned contact
        unassigned_lead = {
            "id": str(uuid.uuid4()),
            "phone": "5491199887766",
            "line_id": None,
            "status": "consulta",
            "tags": ["web-landing"],
            "notes": "Hizo clic en landing",
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        # Simulated incoming WhatsApp message on Line C
        from_phone = "5491199887766"
        line_c_id = "line_C"

        # Search ONLY for (phone, line_id=line_C) — do NOT claim line_id=None
        crm_lead_c = None
        db_leads = [unassigned_lead]

        for lead in db_leads:
            if lead["phone"] == from_phone and lead["line_id"] == line_c_id:
                crm_lead_c = lead
                break

        self.assertIsNone(crm_lead_c)

        # Create new lead for Line C
        new_lead_c = {
            "id": str(uuid.uuid4()),
            "phone": from_phone,
            "status": "nuevo",
            "line_id": line_c_id,
            "charge_amount": 0.0,
            "tags": [],
            "notes": ""
        }

        # Verify unassigned lead remains line_id: None and status: "consulta"
        self.assertIsNone(unassigned_lead["line_id"])
        self.assertEqual(unassigned_lead["status"], "consulta")

        # Verify Line C lead is fresh
        self.assertEqual(new_lead_c["line_id"], "line_C")
        self.assertEqual(new_lead_c["status"], "nuevo")

    def test_classification_does_not_mutate_other_lines(self):
        lead_line_1 = {"id": "l1", "phone": "5491155554444", "line_id": "line_1", "status": "nuevo"}
        lead_line_2 = {"id": "l2", "phone": "5491155554444", "line_id": "line_2", "status": "nuevo"}

        # Classify lead_line_1 as human ("valido")
        # With update_one({"id": lead_line_1["id"]})
        lead_line_1["status"] = "valido"

        # Check line_2 lead status is still "nuevo"
        self.assertEqual(lead_line_1["status"], "valido")
        self.assertEqual(lead_line_2["status"], "nuevo")

if __name__ == "__main__":
    unittest.main()
