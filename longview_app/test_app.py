import unittest
from longview_app.app import app, calculate_age # Import app and specific functions if needed for testing
from datetime import datetime

# Mock patient data similar to what fhir_parser.py would produce
MOCK_PARSED_PATIENTS = [
    {
        "patient_id": "patient-001",
        "full_name": "Walter White",
        "dob": "1959-09-07",
        "gender": "male",
        "insurance": "Chemist's Choice Health",
        "pcp_name": "Dr. Saul Goodman",
        "contact_phone": "505-111-2222",
        "recent_encounters": [
            {"date": "2022-10-20", "type": "Consultation", "facility": "Albuquerque General", "provider": "Dr. Jesse Pinkman", "primary_diagnosis_text": "Cough"}
        ],
        "diagnoses": [
            {"code": "J44.9", "description": "COPD", "status": "active", "category": "encounter-diagnosis"}
        ]
    },
    {
        "patient_id": "patient-002",
        "full_name": "Jesse Bruce Pinkman",
        "dob": "1984-08-24",
        "gender": "male",
        "insurance": "CapnCook Priority Plan",
        "pcp_name": "Dr. Walter White",
        "contact_phone": "505-333-4444",
        "recent_encounters": [],
        "diagnoses": [
            {"code": "F14.10", "description": "Opioid use disorder, mild", "status": "active", "category": "problem-list-item"}
        ]
    },
    {
        "patient_id": "patient-003",
        "full_name": "Skyler White (née Lambert)",
        "dob": "1970-08-11",
        "gender": "female",
        "insurance": "A1 Car Wash Benefits",
        "pcp_name": "Dr. Marie Schrader",
        "contact_phone": "505-555-6666",
        "recent_encounters": [
            {"date": "2023-01-15", "type": "Annual Checkup", "facility": "ABQ Womens Clinic", "provider": "Dr. Marie Schrader", "primary_diagnosis_text": "Healthy"}
        ],
        "diagnoses": []
    }
]

class TestApp(unittest.TestCase):

    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False # Disable CSRF for testing forms if any
        self.client = app.test_client()
        
        # Mock the data used by the app
        # This is crucial: it replaces the live data loading with our controlled mock data
        app.all_patients_data = MOCK_PARSED_PATIENTS 
        # Also update the print statement in app.py for loaded records to reflect mock data
        # Or, even better, the app should ideally get its data via a function that can be mocked.
        # For now, directly patching the global variable all_patients_data.

    def test_index_get(self):
        """Test the main page (GET request) loads correctly."""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome to OneView", response.data) # Check for welcome message
        self.assertNotIn(b"Search Results", response.data) # No search results on initial load

    def test_search_by_patient_id_exact_match_found(self):
        """Test search by an existing patient ID."""
        response = self.client.post('/', data={'search_query': 'patient-001'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Search Results (1 found)", response.data)
        self.assertIn(b"Walter White", response.data)
        self.assertNotIn(b"Jesse Bruce Pinkman", response.data)

    def test_search_by_patient_id_not_found(self):
        """Test search by a non-existent patient ID."""
        response = self.client.post('/', data={'search_query': 'patient-999'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No patients found matching: &quot;patient-999&quot;", response.data)
        self.assertNotIn(b"Walter White", response.data)

    def test_search_by_patient_name_partial_match_found(self):
        """Test search by partial patient name (case-insensitive)."""
        response = self.client.post('/', data={'search_query': 'white'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Search Results (2 found)", response.data)
        self.assertIn(b"Walter White", response.data)
        self.assertIn(b"Skyler White", response.data)
        self.assertNotIn(b"Jesse Bruce Pinkman", response.data)

    def test_search_by_patient_name_case_insensitive(self):
        """Test search by name is case-insensitive."""
        response = self.client.post('/', data={'search_query': 'WALTER white'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Search Results (1 found)", response.data)
        self.assertIn(b"Walter White", response.data)

    def test_search_by_patient_name_not_found(self):
        """Test search by a non-existent patient name."""
        response = self.client.post('/', data={'search_query': 'Gus Fring'})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"No patients found matching: &quot;Gus Fring&quot;", response.data)

    def test_search_empty_query(self):
        """Test search with an empty query."""
        response = self.client.post('/', data={'search_query': ' '}) # Empty or whitespace
        self.assertEqual(response.status_code, 200)
        # Depending on desired behavior for empty search, adjust assertion.
        # Current app.py logic shows "No patients found" for empty POST search.
        self.assertIn(b"No patients found matching: &quot; &quot;", response.data)


    def test_view_patient_detail_found(self):
        """Test viewing a specific patient's detail page."""
        response = self.client.get('/?patient_id=patient-002')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Jesse Bruce Pinkman", response.data)
        self.assertIn(b"DOB: 1984-08-24", response.data)
        self.assertIn(b"Opioid use disorder, mild", response.data) # Check for diagnosis
        self.assertNotIn(b"Search Results", response.data) # Detail view, not search results in main content

    def test_view_patient_detail_not_found(self):
        """Test viewing detail for a non-existent patient ID."""
        response = self.client.get('/?patient_id=patient-999')
        self.assertEqual(response.status_code, 200) # Page loads
        # Expecting a "patient not found" message or similar, or just the welcome page if not handled gracefully.
        # Current app.py logic will render the template with selected_patient=None
        self.assertIn(b"Welcome to OneView", response.data) # Falls back to welcome if patient not found
        self.assertNotIn(b"patient-999", response.data) # Patient ID should not be displayed if not found
        self.assertNotIn(b"DOB:", response.data) # No patient details should be shown

    def test_calculate_age_valid_dob(self):
        """Test age calculation utility."""
        self.assertEqual(calculate_age("1990-01-01"), datetime.today().year - 1990 - ((datetime.today().month, datetime.today().day) < (1, 1)))
        # A more robust way to test age for dates around now:
        today = datetime.today()
        # Birthday today
        dob_today_str = today.strftime("%Y-%m-%d")
        self.assertEqual(calculate_age(dob_today_str), 0)
        # Birthday yesterday
        # dob_yesterday = today - timedelta(days=1)
        # self.assertEqual(calculate_age(dob_yesterday.strftime("%Y-%m-%d")), 0) # Still 0 if not passed birthday this year

    def test_calculate_age_invalid_dob(self):
        self.assertIsNone(calculate_age("invalid-date"))
        self.assertIsNone(calculate_age(None))
        self.assertIsNone(calculate_age("2000-13-01")) # Invalid month

    def test_back_to_search_link(self):
        """Ensure the back to search link is present on detail view and works."""
        response = self.client.get('/?patient_id=patient-001')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"&larr; Back to Search Results", response.data)
        # Further test could involve clicking it if using a more advanced test client like Selenium,
        # but for unit tests, checking presence is usually sufficient.

if __name__ == '__main__':
    # To make sure the app context is available for `app.all_patients_data` modification
    with app.app_context():
        app.all_patients_data = MOCK_PARSED_PATIENTS # Ensure it's set before tests run if run directly
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

