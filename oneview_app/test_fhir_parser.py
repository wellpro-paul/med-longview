import unittest
import json
import os
from oneview_app.fhir_parser import parse_fhir_bundle, load_all_patients_data, DATA_DIR

# --- Mock FHIR Data ---
MOCK_PATIENT_BUNDLE_FULL = {
    "resourceType": "Bundle",
    "id": "test-bundle-full",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "patient-1",
                "name": [{"given": ["John", "Middle"], "family": "Doe"}],
                "birthDate": "1990-01-01",
                "gender": "male",
                "telecom": [
                    {"system": "phone", "use": "home", "value": "555-1234"},
                    {"system": "email", "value": "john.doe@example.com"}
                ],
                "generalPractitioner": [{"reference": "Practitioner/gp-1", "display": "Dr. General Pract"}]
            }
        },
        {
            "resource": {
                "resourceType": "Coverage",
                "id": "coverage-1",
                "type": {"coding": [{"system": "http://hl7.org/fhir/coverage-class", "code": "health"}]},
                "payor": [{"display": "Awesome Health Inc."}]
            }
        },
        {
            "resource": {
                "resourceType": "Encounter",
                "id": "encounter-1",
                "status": "finished",
                "period": {"start": "2023-01-15T10:00:00Z", "end": "2023-01-15T10:30:00Z"},
                "type": [{"text": "Routine Checkup"}],
                "serviceProvider": {"display": "General Hospital"},
                "participant": [
                    {
                        "type": [{"coding": [{"system": "http://hl7.org/fhir/v3/ParticipationType", "code": "PCP"}]}],
                        "individual": {"reference": "Practitioner/pcp-1", "display": "Dr. Primary Care"}
                    }
                ],
                "diagnosis": [
                    {
                        "condition": {"display": "Hypertension"},
                        "use": {"coding": [{"code": "primary"}]}
                    }
                ]
            }
        },
        {
            "resource": {
                "resourceType": "Encounter",
                "id": "encounter-2", # More recent encounter
                "status": "finished",
                "period": {"start": "2023-03-20T14:00:00Z"},
                "type": [{"coding": [{"display": "Specialist Visit"}]}],
                "serviceProvider": {"display": "Specialty Clinic"},
                "participant": [
                     {
                        "individual": {"reference": "Practitioner/spec-1", "display": "Dr. Spectialist"}
                    }
                ],
                 "diagnosis": [
                    {
                        "condition": {"display": "Type 2 Diabetes"},
                        "use": {"coding": [{"code": "AD"}]} # Admission diagnosis
                    }
                ]
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "condition-1",
                "clinicalStatus": {"coding": [{"code": "active"}]},
                "verificationStatus": {"coding": [{"code": "confirmed"}]},
                "category": [{"coding": [{"code": "encounter-diagnosis"}]}],
                "code": {"text": "Essential hypertension", "coding": [{"system": "http://snomed.info/sct", "code": "59621000", "display": "Essential hypertension"}]},
            }
        },
        {
            "resource": {
                "resourceType": "Condition",
                "id": "condition-2",
                "clinicalStatus": {"coding": [{"code": "resolved"}]},
                "category": [{"text": "Problem List Item"}], # Using text for category
                "code": {"text": "Sprained Ankle"},
            }
        }
    ]
}

MOCK_PATIENT_BUNDLE_MINIMAL = {
    "resourceType": "Bundle",
    "id": "test-bundle-minimal",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "patient-2",
                "name": [{"family": "Smith"}], # Only family name
                "birthDate": "1985-05-12",
                # No gender, no telecom, no generalPractitioner
            }
        },
        {
            "resource": { # Coverage with identifier, not display
                "resourceType": "Coverage",
                "id": "coverage-2",
                "payor": [{"identifier": {"value": "MINIMAL_INSURANCE_ID"}}]
            }
        }
        # No encounters, no conditions
    ]
}

MOCK_PATIENT_BUNDLE_NO_PCP_IN_ENCOUNTER = {
    "resourceType": "Bundle",
    "id": "test-bundle-no-pcp-encounter",
    "entry": [
        {
            "resource": {
                "resourceType": "Patient",
                "id": "patient-3",
                "name": [{"given": ["Alice"], "family": "Wonderland"}],
                "birthDate": "2000-10-10",
                "generalPractitioner": [{"display": "Dr. Cheshire Cat (GP)"}] # GP specified at Patient level
            }
        },
        {
            "resource": {
                "resourceType": "Encounter",
                "id": "encounter-3",
                "status": "finished",
                "period": {"start": "2023-02-01T00:00:00Z"},
                "type": [{"text": "Follow-up"}],
                "participant": [ # No PCP coded participant
                    {
                        "individual": {"display": "Nurse Hatter"}
                    }
                ]
            }
        }
    ]
}


class TestFhirParser(unittest.TestCase):

    def test_parse_patient_full(self):
        parsed = parse_fhir_bundle(MOCK_PATIENT_BUNDLE_FULL)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["patient_id"], "patient-1")
        self.assertEqual(parsed["full_name"], "John Middle Doe")
        self.assertEqual(parsed["dob"], "1990-01-01")
        self.assertEqual(parsed["gender"], "male")
        self.assertEqual(parsed["insurance"], "Awesome Health Inc.")
        self.assertEqual(parsed["pcp_name"], "Dr. Primary Care") # From Encounter
        self.assertEqual(parsed["contact_phone"], "555-1234")
        
        self.assertEqual(len(parsed["recent_encounters"]), 2)
        encounter1 = next(e for e in parsed["recent_encounters"] if e["date"] == "2023-01-15T10:00:00Z")
        encounter2 = next(e for e in parsed["recent_encounters"] if e["date"] == "2023-03-20T14:00:00Z")

        self.assertEqual(encounter1["type"], "Routine Checkup")
        self.assertEqual(encounter1["facility"], "General Hospital")
        self.assertEqual(encounter1["provider"], "Dr. Primary Care")
        self.assertEqual(encounter1["primary_diagnosis_text"], "Hypertension")

        self.assertEqual(encounter2["type"], "Specialist Visit")
        self.assertEqual(encounter2["facility"], "Specialty Clinic")
        self.assertEqual(encounter2["provider"], "Dr. Spectialist")
        self.assertEqual(encounter2["primary_diagnosis_text"], "Type 2 Diabetes")

        self.assertEqual(len(parsed["diagnoses"]), 2)
        diag1 = parsed["diagnoses"][0]
        self.assertEqual(diag1["code"], "59621000")
        self.assertEqual(diag1["description"], "Essential hypertension")
        self.assertEqual(diag1["status"], "active")
        self.assertEqual(diag1["category"], "encounter-diagnosis")

        diag2 = parsed["diagnoses"][1]
        self.assertIsNone(diag2["code"]) # No coding, only text
        self.assertEqual(diag2["description"], "Sprained Ankle")
        self.assertEqual(diag2["status"], "resolved")
        self.assertEqual(diag2["category"], "Problem List Item")


    def test_parse_patient_minimal(self):
        parsed = parse_fhir_bundle(MOCK_PATIENT_BUNDLE_MINIMAL)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["patient_id"], "patient-2")
        self.assertEqual(parsed["full_name"], "Smith") # Only family name
        self.assertEqual(parsed["dob"], "1985-05-12")
        self.assertIsNone(parsed["gender"])
        self.assertEqual(parsed["insurance"], "MINIMAL_INSURANCE_ID") # From identifier
        self.assertIsNone(parsed["pcp_name"])
        self.assertIsNone(parsed["contact_phone"])
        self.assertEqual(len(parsed["recent_encounters"]), 0)
        self.assertEqual(len(parsed["diagnoses"]), 0)

    def test_parse_pcp_from_patient_general_practitioner(self):
        parsed = parse_fhir_bundle(MOCK_PATIENT_BUNDLE_NO_PCP_IN_ENCOUNTER)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["patient_id"], "patient-3")
        self.assertEqual(parsed["pcp_name"], "Dr. Cheshire Cat (GP)") # From Patient.generalPractitioner

    def test_parse_empty_bundle(self):
        parsed = parse_fhir_bundle({})
        self.assertIsNone(parsed) # No patient resource

    def test_parse_bundle_no_patient_resource(self):
        parsed = parse_fhir_bundle({"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Encounter"}}]})
        self.assertIsNone(parsed)

    def test_load_all_patients_data_actual_data(self):
        # This test uses the actual data directory.
        # It's more of an integration test for the loading mechanism.
        # Consider creating a small, dedicated test data subdir for true unit tests of loading.
        
        # Create a temporary test data directory with a subset of files if DATA_DIR is too large
        # For now, we'll assume DATA_DIR is manageable or this test can be slow.
        
        # Check if DATA_DIR exists, if not, this test should be skipped or handled.
        if not os.path.exists(DATA_DIR) or not os.listdir(DATA_DIR):
            self.skipTest(f"Actual data directory {DATA_DIR} is empty or not found. Skipping load test.")

        all_patients = load_all_patients_data()
        self.assertTrue(len(all_patients) > 0, "Expected to load at least one patient record from actual data.")
        
        # Check a few properties of the first loaded patient to ensure parsing happened
        first_patient = all_patients[0]
        self.assertIsNotNone(first_patient.get("patient_id"))
        self.assertIsNotNone(first_patient.get("full_name"))
        # self.assertIsNotNone(first_patient.get("dob")) # DOB might be missing in some records

    def test_load_all_patients_data_non_existent_dir(self):
        patients_data = load_all_patients_data(data_directory="/path/to/non_existent_dir_for_test")
        self.assertEqual(len(patients_data), 0)
        # Also check for print output if possible, or log capturing if implemented

    # Add more tests for edge cases in individual parsing functions if needed
    # For example, test parse_patient_name with various name structures, missing given/family etc.
    # test parse_insurance_info with different payor structures, or missing type.

if __name__ == '__main__':
    unittest.main(argv=['first-arg-is-ignored'], exit=False)

```
