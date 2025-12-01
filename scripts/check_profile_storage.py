"""
Quick debug script to check if profile_summary is being stored correctly
Run this on your server to verify database state
"""
import mysql.connector
import os

# Get DB credentials from environment
db_config = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'slotbooking')
}

print("🔍 Checking profile_summary storage...\n")

try:
    conn = mysql.connector.connect(**db_config)
    cursor = conn.cursor(dictionary=True)
    
    # 1. Check if profile_summary column exists
    print("1️⃣ Checking if profile_summary column exists...")
    cursor.execute("""
        SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE 
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_NAME = 'contacts' 
        AND COLUMN_NAME IN ('profile_summary', 'salutation', 'sentiment', 
                            'email_length_preference', 'communication_frequency')
    """)
    columns = cursor.fetchall()
    
    if columns:
        print("✅ Found columns:")
        for col in columns:
            print(f"   - {col['COLUMN_NAME']}: {col['DATA_TYPE']} (nullable: {col['IS_NULLABLE']})")
    else:
        print("❌ No profile columns found! Run the migration SQL first!")
        exit(1)
    
    # 2. Check if any profiles are stored
    print("\n2️⃣ Checking for stored profiles...")
    cursor.execute("""
        SELECT id, name, contact_email, 
               LENGTH(profile_summary) as summary_length,
               salutation, sentiment, email_length_preference, communication_frequency,
               profile_updated_at, kpis_updated_at
        FROM contacts 
        WHERE profile_summary IS NOT NULL 
        ORDER BY profile_updated_at DESC 
        LIMIT 5
    """)
    profiles = cursor.fetchall()
    
    if profiles:
        print(f"✅ Found {len(profiles)} contacts with profiles:")
        for p in profiles:
            print(f"\n   Contact: {p['name']} ({p['contact_email']})")
            print(f"   - Summary length: {p['summary_length']} chars")
            print(f"   - KPIs: {p['salutation']}, {p['sentiment']}, {p['email_length_preference']}, {p['communication_frequency']}")
            print(f"   - Updated: {p['profile_updated_at']}")
    else:
        print("⚠️ No profiles stored yet! Generate one via UI.")
    
    # 3. Check specific contact (Johanna)
    print("\n3️⃣ Checking Johanna's profile...")
    cursor.execute("""
        SELECT id, name, contact_email, profile_summary, 
               salutation, sentiment, email_length_preference, communication_frequency
        FROM contacts 
        WHERE contact_email LIKE '%johanna%' 
        OR name LIKE '%Johanna%'
        LIMIT 1
    """)
    johanna = cursor.fetchone()
    
    if johanna:
        print(f"✅ Found Johanna: {johanna['name']} ({johanna['contact_email']})")
        if johanna['profile_summary']:
            print(f"   ✅ Profile exists ({len(johanna['profile_summary'])} chars)")
            print(f"   First 200 chars: {johanna['profile_summary'][:200]}...")
            print(f"   KPIs: {johanna['salutation']}, {johanna['sentiment']}, {johanna['email_length_preference']}, {johanna['communication_frequency']}")
        else:
            print(f"   ❌ No profile stored for Johanna!")
    else:
        print("⚠️ Johanna not found in contacts")
    
    cursor.close()
    conn.close()
    
    print("\n✅ Database check complete!")
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
