import asyncio
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from app.auth import get_current_user, firebase_app

class AuthenticationTests(unittest.TestCase):
    def test_missing_header_rejected(self):
        with self.assertRaises(HTTPException) as error:
            asyncio.run(get_current_user(None))
        self.assertEqual(error.exception.status_code, 401)

    def test_missing_credentials_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True), patch('app.auth.firebase_admin.get_app', side_effect=ValueError):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(get_current_user('Bearer arbitrary-long-token'))
        self.assertEqual(error.exception.status_code, 503)

    def test_verified_uid_and_unmodified_token(self):
        with patch('app.auth.firebase_app', return_value='app'), patch('app.auth.auth.verify_id_token', return_value={'uid': 'verified-user'}) as verify:
            self.assertEqual(asyncio.run(get_current_user('Bearer signed-token')), 'verified-user')
            verify.assert_called_once_with('signed-token', app='app')

    def test_invalid_token_rejected(self):
        with patch('app.auth.firebase_app'), patch('app.auth.auth.verify_id_token', side_effect=ValueError('invalid')):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(get_current_user('Bearer invalid'))
        self.assertEqual(error.exception.status_code, 401)

    def test_existing_admin_app_reused(self):
        with patch('app.auth.firebase_admin.get_app', return_value='existing'), patch('app.auth.firebase_admin.initialize_app') as initialize:
            self.assertEqual(firebase_app(), 'existing')
            initialize.assert_not_called()

if __name__ == '__main__':
    unittest.main()
