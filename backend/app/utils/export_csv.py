import csv
from io import StringIO
from typing import List, Dict
from datetime import datetime

def export_clicks_to_csv(clicks: List[Dict]) -> str:
    """Export clicks data to CSV string"""
    output = StringIO()
    
    if not clicks:
        return ""
    
    fieldnames = [
        'id', 'campaign_id', 'ip', 'country', 'device', 'os', 'browser',
        'referrer', 'is_bot', 'is_vpn', 'is_datacenter', 'is_blocked',
        'block_reason', 'behavioral_score', 'created_at'
    ]
    
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    
    for click in clicks:
        row = {k: click.get(k, '') for k in fieldnames}
        if isinstance(row.get('created_at'), datetime):
            row['created_at'] = row['created_at'].isoformat()
        writer.writerow(row)
    
    return output.getvalue()