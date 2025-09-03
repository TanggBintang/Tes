# services/google_service.py - Service Account Version for Both Drive and Sheets
import os
import json
import base64
import logging
import time
from googleapiclient.discovery import build
from google.oauth2 import service_account
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError
from datetime import datetime

logger = logging.getLogger(__name__)

# Scopes untuk Google API - kedua service menggunakan service account
SCOPES = [
    'https://www.googleapis.com/auth/drive',
    'https://www.googleapis.com/auth/spreadsheets'
]

class GoogleService:
    def __init__(self):
        # Get environment variables
        self.parent_folder_id = os.environ.get('PARENT_FOLDER_ID')
        self.owner_email = os.environ.get('OWNER_EMAIL')
        
        # Service account untuk kedua service (Drive dan Sheets)
        self.service_account_key = os.environ.get('GOOGLE_SERVICE_ACCOUNT_KEY')
        
        # Validate required environment variables
        self._validate_environment_variables()
        
        # Services - kedua service menggunakan service account
        self.service_drive = None
        self.service_sheets = None
        self.credentials = None

    def _validate_environment_variables(self):
        """Validate that all required environment variables are set"""
        required_vars = {
            'PARENT_FOLDER_ID': self.parent_folder_id,
            'OWNER_EMAIL': self.owner_email,
            'GOOGLE_SERVICE_ACCOUNT_KEY': self.service_account_key
        }
        
        # Optional vars with defaults
        optional_vars = {
            'SHEET_NAME': os.environ.get('SHEET_NAME', 'Sheet1')
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            logger.error(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
            logger.error("Please set all required environment variables:")
            for var in missing_vars:
                logger.error(f"  - {var}")
            raise ValueError(f"Missing environment variables: {', '.join(missing_vars)}")
        
        # Log configuration
        logger.info("✅ All required environment variables are set")
        logger.info(f"📄 Sheet name: {optional_vars['SHEET_NAME']}")
        
        # Validate sheet name format
        sheet_name = optional_vars['SHEET_NAME']
        if not sheet_name or not sheet_name.strip():
            logger.warning("⚠️ Invalid sheet name, using 'Sheet1' as fallback")
            os.environ['SHEET_NAME'] = 'Sheet1'
        
    def authenticate(self):
        """Authenticate with Google APIs using Service Account for both Drive and Sheets"""
        try:
            # Authenticate with Service Account
            if not self._authenticate_service_account():
                logger.error("❌ Failed to authenticate with Service Account")
                return False
                
            logger.info("✅ Both Drive and Sheets authenticated with Service Account successfully!")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error during authentication: {e}")
            return False

    def _authenticate_service_account(self):
        """Authenticate both services with Service Account"""
        try:
            if not self.service_account_key:
                logger.error("❌ Missing GOOGLE_SERVICE_ACCOUNT_KEY")
                return False
            
            # Decode and load service account
            try:
                service_account_info = json.loads(base64.b64decode(self.service_account_key))
                self.credentials = service_account.Credentials.from_service_account_info(
                    service_account_info,
                    scopes=SCOPES
                )
                logger.info("✅ Service Account credentials loaded from environment variable")
            except Exception as e:
                logger.error(f"❌ Error decoding service account: {e}")
                return False
            
            # Build both services with same credentials
            self.service_drive = build('drive', 'v3', credentials=self.credentials)
            self.service_sheets = build('sheets', 'v4', credentials=self.credentials)
            
            logger.info("✅ Drive service authenticated with Service Account")
            logger.info("✅ Sheets service authenticated with Service Account")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error authenticating with Service Account: {e}")
            return False

    def create_folder(self, folder_name, parent_folder_id=None):
        """Create folder using Service Account Drive service"""
        try:
            if not self.service_drive:
                logger.error("❌ Drive service not authenticated")
                return None
                
            parent_id = parent_folder_id or self.parent_folder_id
            
            # Create folder metadata
            folder_metadata = {
                'name': folder_name,
                'mimeType': 'application/vnd.google-apps.folder',
                'parents': [parent_id] if parent_id else []
            }
            
            # Create folder
            folder = self.service_drive.files().create(
                body=folder_metadata,
                supportsAllDrives=True
            ).execute()
            
            folder_id = folder.get('id')
            logger.info(f"📁 Folder created: {folder_name} (ID: {folder_id})")
            
            # Set folder permissions to be accessible
            self._set_folder_permissions(folder_id)
            
            return folder_id
            
        except Exception as e:
            logger.error(f"❌ Error creating folder: {e}")
            return None

    def _set_folder_permissions(self, folder_id):
        """Set folder permissions to be accessible"""
        try:
            if self.owner_email:
                # Give owner full access
                owner_permission = {
                    'type': 'user',
                    'role': 'owner',
                    'emailAddress': self.owner_email
                }
                
                self.service_drive.permissions().create(
                    fileId=folder_id,
                    body=owner_permission,
                    transferOwnership=True,
                    supportsAllDrives=True
                ).execute()
                
                logger.info(f"✅ Folder ownership transferred to {self.owner_email}")
            
        except Exception as e:
            logger.warning(f"⚠️ Could not set folder permissions: {e}")

    def upload_to_drive(self, file_path, file_name, folder_id):
        """Upload file to Drive using Service Account"""
        try:
            if not self.service_drive:
                logger.error("❌ Drive service not authenticated")
                return None
                
            logger.info(f"📤 Starting Service Account upload: {file_name}")
            
            # File metadata
            file_metadata = {
                'name': file_name,
                'parents': [folder_id]
            }
            
            # Upload with chunked upload for better reliability
            media = MediaFileUpload(
                file_path, 
                resumable=True,
                chunksize=1024*1024  # 1MB chunks
            )
            
            # Create the file
            uploaded_file = self.service_drive.files().create(
                body=file_metadata,
                media_body=media,
                supportsAllDrives=True
            ).execute()
            
            file_id = uploaded_file.get('id')
            logger.info(f"✅ Service Account upload successful: {file_name} -> {file_id}")
            
            return file_id
            
        except Exception as e:
            logger.error(f"❌ Service Account upload failed: {e}")
            return None

    def get_folder_link(self, folder_id):
        """Get shareable link for Google Drive folder"""
        return f"https://drive.google.com/drive/folders/{folder_id}"

    def update_spreadsheet(self, spreadsheet_id, spreadsheet_config, laporan_data):
        """Update Google Spreadsheet using Service Account"""
        try:
            if not self.service_sheets:
                logger.error("❌ Sheets service not authenticated")
                return False
                
            row_data = spreadsheet_config.prepare_row_data(laporan_data, 0)
            
            body = {'values': [row_data]}
            
            result = self.service_sheets.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=spreadsheet_config.get_append_range(),
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"✅ Successfully added row to spreadsheet")
            return True
            
        except Exception as e:
            logger.error(f"❌ Error updating spreadsheet: {e}")
            return False

    def test_service_account_access(self):
        """Test if Service Account access is working for both Drive and Sheets"""
        try:
            drive_ok = False
            sheets_ok = False
            
            # Test Drive access
            if self.service_drive:
                try:
                    folder_info = self.service_drive.files().get(
                        fileId=self.parent_folder_id,
                        supportsAllDrives=True
                    ).execute()
                    logger.info(f"✅ Drive access confirmed - Parent folder: {folder_info.get('name')}")
                    drive_ok = True
                except Exception as e:
                    logger.error(f"❌ Drive access test failed: {e}")
            
            # Test Sheets access (just check if service is built)
            if self.service_sheets:
                logger.info("✅ Sheets service is ready")
                sheets_ok = True
            
            return drive_ok and sheets_ok
            
        except Exception as e:
            logger.error(f"❌ Service Account access test failed: {e}")
            return False

    def get_service_account_info(self):
        """Get service account information"""
        try:
            if not self.credentials:
                return None
            
            # Get service account email from credentials
            service_account_email = getattr(self.credentials, 'service_account_email', 'Unknown')
            
            return {
                'service_account_email': service_account_email,
                'drive_service': 'active' if self.service_drive else 'inactive',
                'sheets_service': 'active' if self.service_sheets else 'inactive',
                'scopes': SCOPES
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting service account info: {e}")
            return None

    def cleanup_service_account_files(self):
        """Clean up old files if needed - with service account this is less critical"""
        logger.info("ℹ️ Service Account cleanup - files are owned by service account")
        return True

    def get_drive_quota_info(self):
        """Get Drive quota information - Service Account has different limits"""
        try:
            if not self.service_drive:
                return None
                
            about = self.service_drive.about().get(
                fields='storageQuota,user'
            ).execute()
            
            storage_quota = about.get('storageQuota', {})
            user_info = about.get('user', {})
            
            # Service accounts typically have different quota structure
            return {
                'type': 'service_account',
                'service_account': user_info.get('emailAddress', 'Unknown'),
                'note': 'Service Account quotas are managed differently than personal accounts'
            }
            
        except Exception as e:
            logger.error(f"❌ Error getting quota info: {e}")
            return {
                'type': 'service_account',
                'note': 'Quota information not available for service accounts'
            }