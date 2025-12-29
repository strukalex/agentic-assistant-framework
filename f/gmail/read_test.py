import wmill
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def main(gmail_resource: str):
    # 1. Load the resource from Windmill
    # This automatically handles the token refresh logic for you
    resource = wmill.get_resource(gmail_resource)
    
    # 2. Convert Windmill resource dict to Google Credentials object
    creds = Credentials(
        token=resource["token"],
        refresh_token=resource.get("refresh_token"),
        token_uri=resource.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=resource.get("client_id"),
        client_secret=resource.get("client_secret"),
        scopes=resource.get("scopes")
    )

    # 3. Build the Gmail service
    service = build('gmail', 'v1', credentials=creds)

    # 4. Fetch last 5 emails (IDs only first)
    print("Fetching last 5 emails...")
    results = service.users().messages().list(userId='me', maxResults=5).execute()
    messages = results.get('messages', [])

    if not messages:
        print("No messages found.")
        return []

    # 5. Get details for each email
    email_data = []
    for msg in messages:
        txt = service.users().messages().get(userId='me', id=msg['id']).execute()
        headers = txt['payload']['headers']
        
        # Extract Subject and From
        subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "No Subject")
        sender = next((h['value'] for h in headers if h['name'] == 'From'), "Unknown")
        
        print(f"Found: {subject} from {sender}")
        email_data.append({"subject": subject, "from": sender, "id": msg['id']})

    return email_data
