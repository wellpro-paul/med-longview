import unittest
from oneview_app.app import app, calculate_age # Import app and specific functions if needed for testing
from datetime import datetime

# Mock patient data similar to what fhir_parser.py would produce
MOCK_PARSED_PATIENTS = [
    {
        "patient_id": "patient-001", # Patient for sorting tests
        "full_name": "Walter White",
        "dob": "1959-09-07",
        "gender": "male",
        "insurance": "Chemist's Choice Health",
        "pcp_name": "Dr. Saul Goodman",
        "contact_phone": "505-111-2222",
        "address_full": "308 Negra Arroyo Lane, Albuquerque, NM",
        "marital_status": "Married",
        "preferred_language": "English",
        "recent_encounters": [
            # Dates are intentionally out of order for testing
            {"date": "2022-10-20", "type": "Consultation", "facility": "Albuquerque General", "provider": "Dr. Jesse Pinkman", "primary_diagnosis_text": "Cough"},
            {"date": "2023-03-15T10:00:00Z", "type": "Follow-up", "facility": "Cancer Center", "provider": "Dr. Delcavoli", "primary_diagnosis_text": "Lung Cancer"},
            {"date": "2021-05-01", "type": "Initial Diagnosis", "facility": "Cancer Center", "provider": "Dr. Delcavoli", "primary_diagnosis_text": "Lung Cancer"},
            {"date": "2023-03-15T09:00:00Z", "type": "Lab Work", "facility": "Cancer Center Lab", "provider": "Lab Tech", "primary_diagnosis_text": "N/A"},
            {"date": None, "type": "Unknown Visit", "facility": "Unknown Facility", "provider": "Unknown", "primary_diagnosis_text": "Unknown"}, # Missing date
            {"date": "Invalid Date String", "type": "Error Visit", "facility": "Error Facility", "provider": "Error", "primary_diagnosis_text": "Error"}, # Malformed date
        ],
        "diagnoses": [
            {"code": "J44.9", "description": "COPD", "status": "active", "category": "encounter-diagnosis"},
            {"code": "C34.90", "description": "Lung Cancer", "status": "active", "category": "problem-list-item"}
        ],
        "medications": [ # Medications for Walter White
            {"name": "Lisinopril 10mg", "authored_on": "2022-01-01T10:00:00Z", "prescriber": "Dr. Eva Core", "dosage": "1 tablet by mouth daily", "status": "active"},
            {"name": "Metformin 500mg", "authored_on": "2021-11-15", "prescriber": "Dr. Eva Core", "dosage": None, "status": "completed"},
            {"name": "Aspirin 81mg (External)", "authored_on": "2023-01-20T10:00:00Z", "prescriber": "Dr. Self Prescribe", "dosage": "1 tablet daily as needed", "status": "active"}
        ]
    },
    {
        "patient_id": "patient-004", # New patient for special character search
        "full_name": "Charles O'Malley",
        "dob": "1975-05-15",
        "gender": "male",
        "insurance": "Faithful Health",
        "pcp_name": "Dr. John Finnegan",
        "contact_phone": "555-000-4444",
        "address_full": "10 Angel Street, Heaven, WA",
        "marital_status": "Single",
        "preferred_language": "English",
        "recent_encounters": [],
        "diagnoses": [],
        "medications": [] # No medications for O'Malley
    },
    {
        "patient_id": "patient-002",
        "full_name": "Jesse Bruce Pinkman",
        "dob": "1984-08-24",
        "gender": "male",
        "insurance": "CapnCook Priority Plan",
        "pcp_name": "Dr. Walter White",
        "contact_phone": "505-333-4444",
        "address_full": "9809 Margo St, Albuquerque, NM",
        "marital_status": "Single",
        "preferred_language": "English",
        "recent_encounters": [], # No encounters
        "diagnoses": [
            {"code": "F14.10", "description": "Opioid use disorder, mild", "status": "active", "category": "problem-list-item"}
        ],
        "medications": [ # Jesse has one medication
             {"name": "Naltrexone 50mg", "authored_on": "2023-05-01", "prescriber": "Dr. Recovery", "dosage": "1 tablet daily", "status": "active"}
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
        "address_full": "308 Negra Arroyo Lane, Albuquerque, NM",
        "marital_status": "Married",
        "preferred_language": "English",
        "recent_encounters": [
            {"date": "2023-01-15", "type": "Annual Checkup", "facility": "ABQ Womens Clinic", "provider": "Dr. Marie Schrader", "primary_diagnosis_text": "Healthy"}
        ],
        "diagnoses": [],
        "medications": None # Test case where 'medications' key might be missing or None
    }
]

class TestApp(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Apply mock data once for the entire test class for efficiency
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        # It's generally better to mock the function that loads data,
        # but for this structure, we patch the global variable.
        # This assumes fhir_parser.load_all_patients_data() is called only once at app startup.
        # If it were called per request, a different mocking strategy (e.g., @patch) would be needed.
        app.all_patients_data = MOCK_PARSED_PATIENTS

    def setUp(self):
        # self.client is created per test method to ensure a clean state for each test,
        # though for GET requests and simple state like this, it might not be strictly necessary.
        self.client = app.test_client()
        self.maxDiff = None # Show full diffs on assertion errors

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
        self.assertIn(b"Opioid use disorder, mild", response.data)
        self.assertNotIn(b"Search Results", response.data)
        self.assertIn(b"9809 Margo St, Albuquerque, NM", response.data)
        self.assertIn(b"Single", response.data)
        self.assertIn(b"English", response.data)
        # Check medication display for Jesse (patient-002)
        self.assertIn(b"Naltrexone 50mg", response.data)
        self.assertIn(b"Dr. Recovery", response.data)


    def test_view_patient_detail_pcp_display(self):
        """Test PCP is correctly displayed on patient detail view."""
        response = self.client.get('/?patient_id=patient-001') # Walter White
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Walter White", response.data)
        # Check for PCP in the demographics section
        self.assertIn(b"<strong>Primary Care Provider (PCP):</strong> Dr. Saul Goodman", response.data)


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

    # --- Tests for Encounter Sorting ---

    def get_table_rows_from_html(self, html_data, table_module_class):
        """Helper to extract table rows from a specific module's table."""
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_data, 'html.parser')
        
        module = soup.find('section', class_=table_module_class)
        if not module: return []
        
        table_container = module.find('div', class_='table-container')
        if not table_container: return []
        
        table = table_container.find('table')
        if not table: return []
        
        tbody = table.find('tbody')
        if not tbody: return []
        
        rows_data = []
        for row in tbody.find_all('tr'):
            cells = [cell.text.strip() for cell in row.find_all('td')]
            rows_data.append(cells)
        return rows_data

    def test_encounter_sorting_default_descending(self):
        """Test encounters are sorted by date descending by default."""
        response = self.client.get('/?patient_id=patient-001')
        self.assertEqual(response.status_code, 200)
        
        # Expected order: most recent first. Malformed/None dates at the end (desc).
        expected_dates_order = [
            "2023-03-15T10:00:00Z", # Most recent valid
            "2023-03-15T09:00:00Z",
            "2022-10-20",
            "2021-05-01",
            "Invalid Date String", # Malformed/None pushed to end by current sort logic for desc
            "N/A"                  # None date becomes N/A
        ]
        
        # It's more robust to check the context variable if easily accessible,
        # but parsing HTML is an alternative for black-box testing of the output.
        encounter_rows = self.get_table_rows_from_html(response.data, 'care-management-module')
        actual_dates = [row[0] for row in encounter_rows if row] # Get date from first cell
        self.assertEqual(actual_dates, expected_dates_order, "Encounters are not sorted by date descending by default.")

    def test_encounter_sorting_explicit_ascending(self):
        """Test encounters are sorted by date ascending when specified."""
        response = self.client.get('/?patient_id=patient-001&sort_by=date&sort_order=asc')
        self.assertEqual(response.status_code, 200)
        
        # Expected order: oldest first. Malformed/None dates at the end (asc).
        expected_dates_order = [
            "2021-05-01",           # Oldest valid
            "2022-10-20",
            "2023-03-15T09:00:00Z",
            "2023-03-15T10:00:00Z",
            "N/A",                  # None date becomes N/A, pushed to end by current sort logic for asc
            "Invalid Date String"   # Malformed pushed to end by current sort logic for asc
        ]
        encounter_rows = self.get_table_rows_from_html(response.data, 'care-management-module')
        actual_dates = [row[0] for row in encounter_rows if row]
        self.assertEqual(actual_dates, expected_dates_order, "Encounters are not sorted by date ascending correctly.")

    def test_encounter_sorting_explicit_descending(self):
        """Test encounters are sorted by date descending when specified explicitly."""
        response = self.client.get('/?patient_id=patient-001&sort_by=date&sort_order=desc')
        self.assertEqual(response.status_code, 200)
        
        expected_dates_order = [
            "2023-03-15T10:00:00Z",
            "2023-03-15T09:00:00Z",
            "2022-10-20",
            "2021-05-01",
            "Invalid Date String",
            "N/A"
        ]
        encounter_rows = self.get_table_rows_from_html(response.data, 'care-management-module')
        actual_dates = [row[0] for row in encounter_rows if row]
        self.assertEqual(actual_dates, expected_dates_order, "Encounters are not sorted by date descending explicitly.")

    # --- New Test Cases from previous subtask (verified still pass) ---

    def test_search_by_name_with_apostrophe(self):
        """Test searching for a name containing an apostrophe."""
        response = self.client.post('/', data={'search_query': "O'Malley"})
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Search Results (1 found)", response.data)
        self.assertIn(b"Charles O&#39;Malley", response.data) # Apostrophe is HTML-escaped

        response_substring = self.client.post('/', data={'search_query': 'malley'})
        self.assertEqual(response_substring.status_code, 200)
        self.assertIn(b"Search Results (1 found)", response_substring.data)
        self.assertIn(b"Charles O&#39;Malley", response_substring.data)

    def test_search_query_persists_in_input(self):
        """Test that the search query is displayed in the input field after searching."""
        search_term = "white"
        response = self.client.post('/', data={'search_query': search_term})
        self.assertEqual(response.status_code, 200)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        search_input = soup.find('input', {'name': 'search_query'})
        self.assertIsNotNone(search_input, "Search input field not found.")
        self.assertEqual(search_input.get('value'), search_term, "Search query does not persist in input field.")

    def test_search_query_with_special_chars_persists_in_input(self):
        """Test that a search query with special characters persists correctly."""
        search_term = "O'Malley"
        response = self.client.post('/', data={'search_query': search_term})
        self.assertEqual(response.status_code, 200)
        
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(response.data, 'html.parser')
        search_input = soup.find('input', {'name': 'search_query'})
        self.assertIsNotNone(search_input, "Search input field not found.")
        self.assertEqual(search_input.get('value'), search_term, "Search query with special chars does not persist.")

    # --- Tests for Medication Display ---
    def test_medication_display_for_patient_with_meds(self):
        """Test medications are displayed correctly for a patient with medications."""
        response = self.client.get('/?patient_id=patient-001') # Walter White has medications
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<h3>Medications</h3>", response.data)

        medication_rows = self.get_table_rows_from_html(response.data, 'medications-module')
        self.assertEqual(len(medication_rows), 3, "Incorrect number of medications displayed.")

        # Check details of one medication (Lisinopril)
        # Expected: ["Lisinopril 10mg", "2022-01-01T10:00:00Z", "Dr. Eva Core", "1 tablet by mouth daily", "active"]
        lisinopril_data = next((row for row in medication_rows if row[0] == "Lisinopril 10mg"), None)
        self.assertIsNotNone(lisinopril_data, "Lisinopril not found in displayed medications.")
        self.assertEqual(lisinopril_data[1], "2022-01-01T10:00:00Z")
        self.assertEqual(lisinopril_data[2], "Dr. Eva Core")
        self.assertEqual(lisinopril_data[3], "1 tablet by mouth daily")
        self.assertEqual(lisinopril_data[4], "active")

        # Check medication with no dosage (Metformin)
        metformin_data = next((row for row in medication_rows if row[0] == "Metformin 500mg"), None)
        self.assertIsNotNone(metformin_data, "Metformin not found.")
        self.assertEqual(metformin_data[3], "N/A", "Dosage for Metformin should be N/A.")


    def test_medication_display_for_patient_no_meds(self):
        """Test 'No medications listed.' message for patient with no medications."""
        response = self.client.get('/?patient_id=patient-004') # O'Malley has no medications
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<h3>Medications</h3>", response.data)
        self.assertIn(b"<p>No medications listed.</p>", response.data)
        
        medication_rows = self.get_table_rows_from_html(response.data, 'medications-module')
        self.assertEqual(len(medication_rows), 0, "Medication table should be empty.")

    def test_medication_display_for_patient_meds_key_is_none(self):
        """Test 'No medications listed.' message for patient where 'medications' key is None."""
        response = self.client.get('/?patient_id=patient-003') # Skyler has medications: None
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<h3>Medications</h3>", response.data)
        self.assertIn(b"<p>No medications listed.</p>", response.data)
        
        medication_rows = self.get_table_rows_from_html(response.data, 'medications-module')
        self.assertEqual(len(medication_rows), 0, "Medication table should be empty for None medications key.")


if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)
