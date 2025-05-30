import json
import os
from datetime import datetime
import logging

# Constants for FHIR resource types and codes
PATIENT_RESOURCE_TYPE = "Patient"
COVERAGE_RESOURCE_TYPE = "Coverage"
ENCOUNTER_RESOURCE_TYPE = "Encounter"
CONDITION_RESOURCE_TYPE = "Condition"
PCP_CODE = "PCP"  # Primary Care Provider code
PRIMARY_CARE_PHYSICIAN_CODE = "primaryCarePhysician"
MEDICATION_REQUEST_RESOURCE_TYPE = "MedicationRequest"
MEDICATION_RESOURCE_TYPE = "Medication"

# Define the path to the FHIR data directory
DATA_DIR = os.path.join(os.path.dirname(__file__), "data", "synthea_sample_data_fhir_latest")

def get_resource_entries(bundle_data, resource_type):
    """Extracts all entries of a specific resource type from a FHIR bundle."""
    return [
        entry["resource"]
        for entry in bundle_data.get("entry", [])
        if entry.get("resource", {}).get("resourceType") == resource_type
    ]

def parse_patient_name(patient_resource):
    """Parses the patient's full name."""
    if not patient_resource or not patient_resource.get("name"):
        return None
    name_data = patient_resource["name"][0]  # Assuming the first name entry is primary
    given_names = " ".join(name_data.get("given", []))
    family_name = name_data.get("family", "")
    return f"{given_names} {family_name}".strip()

def parse_patient_dob(patient_resource):
    """Parses the patient's date of birth."""
    return patient_resource.get("birthDate")

def parse_patient_gender(patient_resource):
    """Parses the patient's gender."""
    return patient_resource.get("gender")

def parse_insurance_info(coverage_resources):
    """Parses insurance information, prioritizing 'display' over 'identifier'."""
    if not coverage_resources:
        return None
    # Assumption: Prioritize coverage entries that look like health insurance
    # This is a heuristic and might need refinement.
    for coverage in coverage_resources:
        if coverage.get("type", {}).get("coding", [{}])[0].get("code") in ["health", "PPO", "HMO"]:
            payor = coverage.get("payor", [{}])[0] # Assuming the first payor is relevant
            if payor.get("display"):
                return payor["display"]
            if payor.get("identifier", {}).get("value"):
                return payor["identifier"]["value"]
    # Fallback to the first coverage entry if no clear primary is found
    payor = coverage_resources[0].get("payor", [{}])[0]
    if payor.get("display"):
        return payor["display"]
    if payor.get("identifier", {}).get("value"):
        return payor["identifier"]["value"]
    return None

def parse_pcp_name(patient_resource, encounter_resources):
    """
    Parses the Primary Care Provider's name.
    Checks Encounters first, then Patient.generalPractitioner.
    """
    # Check Encounters for PCP
    for encounter in encounter_resources:
        for participant in encounter.get("participant", []):
            for type_code in participant.get("type", []):
                for coding in type_code.get("coding", []):
                    if coding.get("code") in [PCP_CODE, PRIMARY_CARE_PHYSICIAN_CODE]:
                        if participant.get("individual", {}).get("display"):
                            return participant["individual"]["display"]

    # Check Patient.generalPractitioner
    general_practitioners = patient_resource.get("generalPractitioner", [])
    if general_practitioners and general_practitioners[0].get("display"):
        return general_practitioners[0]["display"]
    return None

def parse_contact_info(patient_resource):
    """Parses patient's phone contact information."""
    for telecom in patient_resource.get("telecom", []):
        if telecom.get("system") == "phone" and telecom.get("use") in ["home", "mobile"]:
            return telecom.get("value")
    return None

def parse_recent_encounters(encounter_resources):
    """Parses recent encounters/visits."""
    encounters_data = []
    for encounter in encounter_resources:
        encounter_info = {
            "date": encounter.get("period", {}).get("start") or encounter.get("period", {}).get("end"),
            "type": None,
            "facility": encounter.get("serviceProvider", {}).get("display"),
            "provider": None,
            "primary_diagnosis_text": None,
        }

        # Encounter Type
        if encounter.get("type"):
            encounter_type = encounter["type"][0] # Assuming first type is primary
            if encounter_type.get("text"):
                encounter_info["type"] = encounter_type["text"]
            elif encounter_type.get("coding"):
                encounter_info["type"] = encounter_type["coding"][0].get("display")

        # Encounter Provider
        for participant in encounter.get("participant", []):
            # Assuming a practitioner participant is the provider
            if "Practitioner" in participant.get("individual", {}).get("reference", ""):
                 if participant.get("individual", {}).get("display"):
                    encounter_info["provider"] = participant["individual"]["display"]
                    break # Take the first practitioner found

        # Primary Diagnosis Text
        # Assumption: First diagnosis or one marked as 'primary' or 'chief complaint'
        for diagnosis_entry in encounter.get("diagnosis", []):
            use_coding = diagnosis_entry.get("use", {}).get("coding", [{}])[0].get("code")
            if use_coding in ["primary", "chief-complaint", "CC", "admission", "AD"]: # Added more potential primary codes
                if diagnosis_entry.get("condition", {}).get("display"):
                    encounter_info["primary_diagnosis_text"] = diagnosis_entry["condition"]["display"]
                    break
            # Fallback if no 'use' is specified or matches primary indicators
            if not encounter_info["primary_diagnosis_text"] and diagnosis_entry.get("condition", {}).get("display"):
                 encounter_info["primary_diagnosis_text"] = diagnosis_entry["condition"]["display"]


        encounters_data.append(encounter_info)
    return encounters_data

def parse_diagnoses(condition_resources):
    """Parses diagnoses (conditions)."""
    diagnoses_data = []
    for condition in condition_resources:
        condition_info = {
            "code": None,
            "description": None,
            "status": None,
            "category": None,
        }

        # Code and Description
        if condition.get("code", {}).get("coding"):
            # Prefer SNOMED CT codes if available
            snomed_code = next((c.get("code") for c in condition["code"]["coding"] if c.get("system", "").startswith("http://snomed.info/sct")), None)
            snomed_display = next((c.get("display") for c in condition["code"]["coding"] if c.get("system", "").startswith("http://snomed.info/sct")), None)
            if snomed_code:
                condition_info["code"] = snomed_code
                condition_info["description"] = snomed_display or condition["code"].get("text")
            else: # Fallback to the first coding available
                condition_info["code"] = condition["code"]["coding"][0].get("code")
                condition_info["description"] = condition["code"]["coding"][0].get("display") or condition["code"].get("text")
        elif condition.get("code", {}).get("text"):
             condition_info["description"] = condition["code"]["text"]


        # Status
        if condition.get("clinicalStatus", {}).get("coding"):
            condition_info["status"] = condition["clinicalStatus"]["coding"][0].get("code")
        elif condition.get("verificationStatus", {}).get("coding"):
            condition_info["status"] = condition["verificationStatus"]["coding"][0].get("code")

        # Category
        if condition.get("category"):
            category = condition["category"][0] # Assuming first category is primary
            if category.get("coding"):
                condition_info["category"] = category["coding"][0].get("code")
            elif category.get("text"):
                 condition_info["category"] = category.get("text")

        diagnoses_data.append(condition_info)
    return diagnoses_data

def parse_address(patient_resource):
    """Parses the patient's home address."""
    if not patient_resource or not patient_resource.get("address"):
        return None
    
    home_address = None
    for addr in patient_resource.get("address", []):
        if addr.get("use") == "home":
            home_address = addr
            break
    
    if not home_address: # If no 'home' address, take the first one available
        home_address = patient_resource.get("address", [])[0] if patient_resource.get("address") else None

    if not home_address:
        return None

    parts = [
        ", ".join(home_address.get("line", [])), # Join multiple lines if they exist
        home_address.get("city"),
        home_address.get("state"),
        home_address.get("postalCode"),
        home_address.get("country")
    ]
    return ", ".join(p for p in parts if p and p.strip()) # Filter out None or empty parts

def parse_marital_status(patient_resource):
    """Parses the patient's marital status."""
    marital_status_data = patient_resource.get("maritalStatus")
    if not marital_status_data:
        return None
    
    if marital_status_data.get("text"):
        return marital_status_data["text"]
    if marital_status_data.get("coding"):
        coding = marital_status_data["coding"][0] # Assuming first coding is primary
        if coding.get("display"):
            return coding["display"]
    return None

def parse_preferred_language(patient_resource):
    """Parses the patient's preferred language."""
    communications = patient_resource.get("communication", [])
    if not communications:
        return None

    preferred_comm = None
    for comm in communications:
        if comm.get("preferred") is True:
            preferred_comm = comm
            break
    
    if not preferred_comm and communications: # If no 'preferred', take the first one
        preferred_comm = communications[0]

    if not preferred_comm or not preferred_comm.get("language"):
        return None
        
    language_data = preferred_comm["language"]
    if language_data.get("text"):
        return language_data["text"]
    if language_data.get("coding"):
        coding = language_data["coding"][0] # Assuming first coding is primary
        if coding.get("display"):
            return coding["display"]
    return None

def parse_medications(bundle_data):
    """Parses medication data from MedicationRequest and Medication resources."""
    medication_resources = {}
    for entry in bundle_data.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == MEDICATION_RESOURCE_TYPE:
            med_id = entry.get("fullUrl") or f"urn:uuid:{resource.get('id')}"
            if med_id:
                 medication_resources[med_id] = resource

    parsed_med_requests = []
    med_request_entries = get_resource_entries(bundle_data, MEDICATION_REQUEST_RESOURCE_TYPE)

    for med_request in med_request_entries:
        med_info = {
            "name": None,
            "authored_on": med_request.get("authoredOn"),
            "prescriber": med_request.get("requester", {}).get("display"),
            "dosage": med_request.get("dosageInstruction", [{}])[0].get("text"),
            "status": med_request.get("status")
        }

        med_codeable_concept = med_request.get("medicationCodeableConcept")
        med_reference = med_request.get("medicationReference")

        if med_codeable_concept:
            med_info["name"] = med_codeable_concept.get("text")
            if not med_info["name"] and med_codeable_concept.get("coding"):
                med_info["name"] = med_codeable_concept["coding"][0].get("display")
        elif med_reference:
            ref_str = med_reference.get("reference")
            if ref_str in medication_resources:
                linked_med_resource = medication_resources[ref_str]
                if linked_med_resource.get("code", {}).get("text"):
                    med_info["name"] = linked_med_resource["code"]["text"]
                elif linked_med_resource.get("code", {}).get("coding"):
                    med_info["name"] = linked_med_resource["code"]["coding"][0].get("display")
                else:
                    med_info["name"] = "Unknown (Name not found in referenced Medication)"
                    logging.warning(f"Medication name not found in referenced Medication resource: {ref_str} for MedicationRequest {med_request.get('id', 'N/A')}")

            else:
                med_info["name"] = med_reference.get("display") or f"Unknown (Reference {ref_str} not found)"
                logging.warning(f"MedicationReference {ref_str} not found in bundle for MedicationRequest {med_request.get('id', 'N/A')}")
        
        if not med_info["name"]:
            med_info["name"] = "Unknown Medication"
            logging.warning(f"Could not determine medication name for MedicationRequest {med_request.get('id', 'N/A')}")

        parsed_med_requests.append(med_info)
    return parsed_med_requests

def parse_fhir_bundle(bundle_data):
    """Parses a single FHIR patient bundle."""
    patient_resource_list = get_resource_entries(bundle_data, PATIENT_RESOURCE_TYPE)
    if not patient_resource_list:
        bundle_id = bundle_data.get("id", "Unknown Bundle ID")
        logging.warning(f"No Patient resource found in bundle: {bundle_id}")
        return None 
    patient_resource = patient_resource_list[0]

    coverage_resources = get_resource_entries(bundle_data, COVERAGE_RESOURCE_TYPE)
    encounter_resources = get_resource_entries(bundle_data, ENCOUNTER_RESOURCE_TYPE)
    condition_resources = get_resource_entries(bundle_data, CONDITION_RESOURCE_TYPE)
    
    parsed_patient = {
        "patient_id": patient_resource.get("id"),
        "full_name": parse_patient_name(patient_resource),
        "dob": parse_patient_dob(patient_resource),
        "gender": parse_patient_gender(patient_resource),
        "insurance": parse_insurance_info(coverage_resources),
        "pcp_name": parse_pcp_name(patient_resource, encounter_resources),
        "contact_phone": parse_contact_info(patient_resource),
        "address_full": parse_address(patient_resource),
        "marital_status": parse_marital_status(patient_resource),
        "preferred_language": parse_preferred_language(patient_resource),
        "recent_encounters": parse_recent_encounters(encounter_resources),
        "diagnoses": parse_diagnoses(condition_resources),
        "medications": parse_medications(bundle_data),
    }
    return parsed_patient

def load_all_patients_data(data_directory=DATA_DIR):
    """Loads and parses all patient FHIR JSON files from the specified directory."""
    all_patients = []
    if not os.path.exists(data_directory):
        print(f"Error: Data directory not found at {data_directory}")
        return all_patients

    for filename in os.listdir(data_directory):
        if filename.endswith(".json"):
            filepath = os.path.join(data_directory, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    bundle_data = json.load(f)
                    parsed_patient = parse_fhir_bundle(bundle_data)
                    if parsed_patient:
                        all_patients.append(parsed_patient)
            except json.JSONDecodeError:
                print(f"Error decoding JSON from file: {filename}")
            except Exception as e:
                print(f"Error processing file {filename}: {e}")
    return all_patients

if __name__ == "__main__":
    print(f"Loading patient data from: {DATA_DIR}")
    patients_data = load_all_patients_data()

    if patients_data:
        print(f"\nSuccessfully parsed {len(patients_data)} patient records.\n")
        print("Showing summary for a few patients:")
        for i, patient in enumerate(patients_data[:3]): # Print summary for the first 3 patients
            print(f"\n--- Patient {i+1} ---")
            print(f"  Name: {patient.get('full_name')}")
            print(f"  DOB: {patient.get('dob')}")
            print(f"  Insurance: {patient.get('insurance')}")
            print(f"  PCP: {patient.get('pcp_name')}")
            print(f"  Number of Encounters: {len(patient.get('recent_encounters', []))}")
            # Print details of the first encounter if available
            if patient.get('recent_encounters'):
                first_encounter = patient['recent_encounters'][0]
                print(f"    First Encounter Date: {first_encounter.get('date')}")
                print(f"    First Encounter Type: {first_encounter.get('type')}")
                print(f"    First Encounter Facility: {first_encounter.get('facility')}")
                print(f"    First Encounter Provider: {first_encounter.get('provider')}")
                print(f"    First Encounter Diagnosis: {first_encounter.get('primary_diagnosis_text')}")

            print(f"  Number of Conditions: {len(patient.get('diagnoses', []))}")
            # Print details of the first condition if available
            if patient.get('diagnoses'):
                first_diagnosis = patient['diagnoses'][0]
                print(f"    First Condition Code: {first_diagnosis.get('code')}")
                print(f"    First Condition Description: {first_diagnosis.get('description')}")
                print(f"    First Condition Status: {first_diagnosis.get('status')}")
                print(f"    First Condition Category: {first_diagnosis.get('category')}")
    else:
        print("No patient data was loaded or parsed.")

    # Example of accessing a specific patient's data for further processing if needed
    # if len(patients_data) > 0:
    #     specific_patient = patients_data[0]
    #     print(f"\n\nExample: Accessing data for {specific_patient.get('full_name')}")
    #     print(f"All diagnoses for {specific_patient.get('full_name')}:")
    #     for diag in specific_patient.get('diagnoses', []):
    #         print(f"  - {diag.get('description')} (Code: {diag.get('code')}, Status: {diag.get('status')})")

