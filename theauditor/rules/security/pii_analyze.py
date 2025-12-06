"""PII Data Analyzer - Comprehensive International Edition.

Detects PII exposure issues:
- Direct PII in assignments (CWE-359)
- PII logged to console/files (CWE-532)
- PII in error responses (CWE-209)
- PII in URLs/query strings (CWE-598)
- Unencrypted PII storage (CWE-311)
- PII in client-side storage (CWE-922)
- PII access without authorization (CWE-862)
"""

import re
from enum import Enum
from functools import lru_cache

from theauditor.rules.base import (
    Confidence,
    RuleMetadata,
    RuleResult,
    Severity,
    StandardFinding,
    StandardRuleContext,
)
from theauditor.rules.fidelity import RuleDB
from theauditor.rules.query import Q

METADATA = RuleMetadata(
    name="pii_exposure",
    category="security",
    target_extensions=[".py", ".js", ".ts", ".jsx", ".tsx"],
    exclude_patterns=["test/", "spec.", "__tests__", "demo/"],
    execution_scope="database",
    primary_table="assignments",
)


class PrivacyRegulation(Enum):
    """Privacy regulations that may be violated."""

    GDPR = "GDPR (EU General Data Protection Regulation)"
    CCPA = "CCPA (California Consumer Privacy Act)"
    COPPA = "COPPA (Children's Online Privacy Protection Act)"
    HIPAA = "HIPAA (Health Insurance Portability and Accountability Act)"
    PCI_DSS = "PCI-DSS (Payment Card Industry Data Security Standard)"
    PIPEDA = "PIPEDA (Personal Information Protection and Electronic Documents Act)"
    LGPD = "LGPD (Brazilian General Data Protection Law)"
    POPI = "POPI (Protection of Personal Information Act - South Africa)"
    FERPA = "FERPA (Family Educational Rights and Privacy Act)"
    BIPA = "BIPA (Biometric Information Privacy Act)"
    GLBA = "GLBA (Gramm-Leach-Bliley Act)"
    SOX = "SOX (Sarbanes-Oxley Act)"
    Privacy_Act = "Privacy Act (Australia)"
    PDPA = "PDPA (Personal Data Protection Act - Singapore)"
    APPs = "APPs (Australian Privacy Principles)"


US_GOVERNMENT_IDS = frozenset(
    [
        "ssn",
        "social_security",
        "social_security_number",
        "socialsecuritynumber",
        "ein",
        "employer_identification",
        "federal_tax_id",
        "itin",
        "individual_taxpayer_identification",
        "passport",
        "passport_number",
        "passport_no",
        "drivers_license",
        "driver_license",
        "driving_license",
        "dl_number",
        "state_id",
        "state_identification",
        "military_id",
        "dod_id",
        "defense_id",
        "voter_registration",
        "voter_id",
        "medicare_number",
        "medicare_id",
        "medicaid_number",
        "medicaid_id",
        "dea_number",
        "dea_registration",
        "npi",
        "national_provider_identifier",
        "upin",
        "unique_physician_identification",
        "green_card",
        "permanent_resident_card",
        "alien_registration",
        "naturalization_certificate",
        "citizenship_certificate",
        "visa_number",
        "visa_id",
        "i94_number",
    ]
)


INTERNATIONAL_GOVERNMENT_IDS = frozenset(
    [
        "social_insurance_number",
        "nas",
        "numero_assurance_sociale",
        "health_card_number",
        "ohip",
        "ramq",
        "msp",
        "ni_number",
        "national_insurance",
        "nhs_number",
        "nhs_id",
        "chi_number",
        "community_health_index",
        "hcn",
        "health_care_number",
        "driving_licence_uk",
        "dvla_number",
        "vat_number",
        "vat_id",
        "eu_vat",
        "eori_number",
        "pesel",
        "cnp",
        "oib",
        "jmbg",
        "egn",
        "rodne_cislo",
        "isikukood",
        "henkilotunnus",
        "insee",
        "nir",
        "steuer_id",
        "steueridentifikationsnummer",
        "amka",
        "taj",
        "pps_number",
        "codice_fiscale",
        "asmens_kodas",
        "cnp_luxembourg",
        "idkaart",
        "nif",
        "nie",
        "dni",
        "personnummer",
        "ahv",
        "avs",
        "aadhaar",
        "aadhar",
        "uid",
        "pan_card",
        "pan_number",
        "voter_id_india",
        "ration_card",
        "nric",
        "fin_number",
        "foreign_identification_number",
        "mykad",
        "id_card_hk",
        "hkid",
        "arc",
        "alien_registration_card",
        "rrn",
        "resident_registration",
        "my_number",
        "kojin_bango",
        "tfn",
        "tax_file_number",
        "ird_number",
        "citizen_id",
        "cmnd",
        "cccd",
        "nik",
        "philhealth",
        "umid",
        "cpf",
        "registro_geral",
        "rg_number",
        "cnpj",
        "curp",
        "rfc",
        "ine",
        "rut",
        "cedula",
        "dui",
        "cui",
        "cuit",
        "cuil",
        "national_id_sa",
        "emirates_id",
        "qid",
        "civil_id_kw",
        "national_id_eg",
        "id_number_za",
        "omang",
        "nin_ng",
        "huduma_number",
        "nida",
        "national_id_il",
        "tc_kimlik",
    ]
)


HEALTHCARE_PII = frozenset(
    [
        "medical_record_number",
        "mrn",
        "patient_id",
        "patient_number",
        "health_record",
        "ehr_id",
        "emr_number",
        "chart_number",
        "case_number",
        "encounter_id",
        "insurance_policy",
        "policy_number",
        "member_id",
        "subscriber_id",
        "group_number",
        "plan_id",
        "benefit_id",
        "claim_number",
        "authorization_number",
        "prior_auth",
        "copay_card",
        "rx_bin",
        "rx_pcn",
        "rx_group",
        "diagnosis",
        "diagnosis_code",
        "icd_code",
        "icd10",
        "icd9",
        "procedure_code",
        "cpt_code",
        "hcpcs_code",
        "lab_result",
        "test_result",
        "blood_type",
        "medication",
        "prescription",
        "rx_number",
        "ndc_code",
        "allergy",
        "medical_condition",
        "disability",
        "mental_health",
        "psychiatric_record",
        "substance_abuse",
        "addiction_treatment",
        "hiv_status",
        "aids_status",
        "std_test",
        "pregnancy_status",
        "genetic_information",
        "dna_sequence",
        "clinical_trial_id",
        "study_id",
        "protocol_number",
        "physician_name",
        "doctor_name",
        "provider_npi",
        "dea_number",
        "license_number_medical",
        "hospital_id",
        "facility_id",
        "clinic_id",
        "appointment_id",
        "visit_number",
        "admission_date",
        "discharge_date",
        "procedure_date",
        "surgery_date",
        "blood_pressure",
        "heart_rate",
        "temperature",
        "weight",
        "height",
        "bmi",
        "glucose_level",
        "oxygen_saturation",
        "respiration_rate",
    ]
)


FINANCIAL_PII = frozenset(
    [
        "credit_card",
        "credit_card_number",
        "cc_number",
        "card_number",
        "debit_card",
        "payment_card",
        "primary_account_number",
        "card_pan",
        "cvv",
        "cvv2",
        "cvc",
        "cvc2",
        "card_verification",
        "card_expiry",
        "expiry_date",
        "expiration_date",
        "cardholder_name",
        "name_on_card",
        "bank_account",
        "account_number",
        "checking_account",
        "savings_account",
        "routing_number",
        "aba_number",
        "swift_code",
        "bic_code",
        "iban",
        "international_bank_account",
        "sort_code",
        "bsb_number",
        "branch_code",
        "bank_name",
        "financial_institution",
        "brokerage_account",
        "trading_account",
        "investment_account",
        "portfolio_id",
        "custody_account",
        "margin_account",
        "retirement_account",
        "401k",
        "ira_account",
        "roth_ira",
        "pension_number",
        "annuity_number",
        "stock_symbol",
        "cusip",
        "isin",
        "sedol",
        "paypal_account",
        "paypal_email",
        "venmo_handle",
        "cashapp_tag",
        "zelle_id",
        "crypto_wallet",
        "bitcoin_address",
        "ethereum_address",
        "wallet_address",
        "private_key",
        "seed_phrase",
        "mnemonic_phrase",
        "stripe_customer_id",
        "square_customer_id",
        "payment_token",
        "payment_method_id",
        "tax_id",
        "tax_return",
        "w2_form",
        "w9_form",
        "1099_form",
        "income",
        "salary",
        "wage",
        "compensation",
        "bonus",
        "credit_score",
        "fico_score",
        "credit_report",
        "loan_number",
        "mortgage_number",
        "lease_number",
        "insurance_claim",
        "claim_number",
        "policy_number",
        "billing_address",
        "invoice_number",
        "purchase_order",
        "transaction_id",
        "payment_id",
        "order_id",
        "receipt_number",
    ]
)


CHILDREN_PII = frozenset(
    [
        "student_id",
        "student_number",
        "school_id",
        "district_id",
        "enrollment_id",
        "registration_number",
        "grade_level",
        "gpa",
        "transcript",
        "report_card",
        "standardized_test_score",
        "sat_score",
        "act_score",
        "iep",
        "individualized_education_program",
        "504_plan",
        "special_education_record",
        "attendance_record",
        "disciplinary_record",
        "lunch_number",
        "bus_number",
        "locker_number",
        "birth_certificate_number",
        "adoption_record",
        "foster_care_id",
        "case_worker",
        "custody_agreement",
        "child_support_case",
        "juvenile_record",
        "immunization_record",
        "vaccination_record",
        "pediatrician",
        "emergency_contact",
        "parental_consent",
        "coppa_consent",
        "child_email",
        "child_username",
        "gamer_tag",
        "minecraft_username",
        "roblox_username",
        "fortnite_id",
        "youtube_kids_account",
        "tiktok_handle",
        "screen_time_passcode",
        "parental_control_pin",
        "school_schedule",
        "after_school_activity",
        "sports_team",
        "club_membership",
        "camp_registration",
        "daycare_id",
        "pickup_authorization",
        "carpool_info",
    ]
)


BIOMETRIC_PII = frozenset(
    [
        "fingerprint",
        "finger_print",
        "thumbprint",
        "facial_recognition",
        "face_id",
        "facial_template",
        "iris_scan",
        "retina_scan",
        "eye_scan",
        "voice_print",
        "voice_recognition",
        "speaker_verification",
        "palm_print",
        "hand_geometry",
        "vein_pattern",
        "dna_profile",
        "genetic_marker",
        "genome_sequence",
        "gait_analysis",
        "walking_pattern",
        "keystroke_dynamics",
        "typing_pattern",
        "signature_biometric",
        "handwriting_pattern",
        "photo",
        "photograph",
        "headshot",
        "profile_picture",
        "video_recording",
        "cctv_footage",
        "surveillance_video",
        "height",
        "weight",
        "eye_color",
        "hair_color",
        "distinguishing_marks",
        "tattoo",
        "scar",
        "birthmark",
        "body_measurements",
        "clothing_size",
        "shoe_size",
        "behavioral_pattern",
        "usage_pattern",
        "interaction_pattern",
        "mouse_movement",
        "touch_pattern",
        "swipe_pattern",
        "app_usage",
        "browsing_pattern",
        "purchase_pattern",
        "sleep_pattern",
        "exercise_data",
        "heart_rate_pattern",
        "stress_level",
        "mood_data",
        "emotion_recognition",
    ]
)


DIGITAL_IDENTITY_PII = frozenset(
    [
        "username",
        "user_name",
        "login_name",
        "account_name",
        "password",
        "passwd",
        "pwd",
        "passcode",
        "pin",
        "security_question",
        "security_answer",
        "secret_question",
        "two_factor_code",
        "2fa_code",
        "totp_code",
        "otp",
        "backup_code",
        "recovery_code",
        "reset_token",
        "api_key",
        "api_secret",
        "api_token",
        "access_token",
        "refresh_token",
        "bearer_token",
        "auth_token",
        "session_id",
        "session_token",
        "session_key",
        "cookie_id",
        "tracking_cookie",
        "auth_cookie",
        "jwt_token",
        "json_web_token",
        "id_token",
        "user_id",
        "userid",
        "uid",
        "uuid",
        "guid",
        "customer_id",
        "client_id",
        "member_id",
        "device_id",
        "machine_id",
        "hardware_id",
        "mac_address",
        "imei",
        "imsi",
        "udid",
        "android_id",
        "advertising_id",
        "idfa",
        "aaid",
        "push_token",
        "fcm_token",
        "apns_token",
        "browser_fingerprint",
        "canvas_fingerprint",
        "email",
        "email_address",
        "primary_email",
        "recovery_email",
        "phone",
        "phone_number",
        "mobile_number",
        "cell_phone",
        "work_phone",
        "home_phone",
        "fax_number",
        "profile_url",
        "avatar_url",
        "public_key",
        "pgp_key",
    ]
)


LOCATION_PII = frozenset(
    [
        "home_address",
        "residential_address",
        "mailing_address",
        "shipping_address",
        "billing_address",
        "work_address",
        "street_address",
        "street_name",
        "house_number",
        "apartment_number",
        "unit_number",
        "suite_number",
        "po_box",
        "postal_box",
        "mail_stop",
        "city",
        "state",
        "province",
        "region",
        "zip_code",
        "zipcode",
        "postal_code",
        "postcode",
        "country",
        "country_code",
        "latitude",
        "longitude",
        "coordinates",
        "gps_location",
        "geolocation",
        "geo_coordinates",
        "map_location",
        "plus_code",
        "what3words",
        "grid_reference",
        "altitude",
        "elevation",
        "floor_level",
        "ip_address",
        "ipv4",
        "ipv6",
        "public_ip",
        "private_ip",
        "subnet",
        "network_address",
        "gateway_ip",
        "wifi_ssid",
        "wifi_bssid",
        "access_point",
        "cell_tower_id",
        "base_station",
        "network_operator",
        "flight_number",
        "seat_number",
        "boarding_pass",
        "frequent_flyer",
        "airline_member_id",
        "hotel_reservation",
        "booking_reference",
        "car_rental",
        "rental_agreement",
        "train_ticket",
        "bus_pass",
        "metro_card",
        "toll_tag",
        "ez_pass",
        "fastrak",
        "parking_permit",
        "garage_access",
        "travel_itinerary",
        "trip_details",
    ]
)


EMPLOYMENT_PII = frozenset(
    [
        "employee_id",
        "employee_number",
        "staff_id",
        "badge_number",
        "work_email",
        "corporate_email",
        "company_email",
        "job_title",
        "position",
        "department",
        "division",
        "manager_name",
        "supervisor",
        "team_lead",
        "hire_date",
        "start_date",
        "termination_date",
        "employment_status",
        "contract_type",
        "salary",
        "base_pay",
        "hourly_rate",
        "pay_rate",
        "bonus",
        "commission",
        "overtime_pay",
        "stock_options",
        "rsu",
        "equity_grant",
        "benefits_id",
        "health_plan",
        "dental_plan",
        "vision_plan",
        "life_insurance",
        "disability_insurance",
        "401k_contribution",
        "pension_contribution",
        "paid_time_off",
        "pto_balance",
        "sick_leave",
        "performance_review",
        "evaluation",
        "rating",
        "disciplinary_action",
        "warning",
        "suspension",
        "promotion_record",
        "transfer_record",
        "training_record",
        "certification",
        "license",
        "background_check",
        "drug_test",
        "security_clearance",
        "i9_verification",
        "work_authorization",
        "union_membership",
        "union_id",
        "professional_license",
        "bar_number",
        "medical_license",
        "teaching_license",
        "contractor_license",
        "real_estate_license",
        "broker_number",
        "cpa_number",
        "registration_number",
        "linkedin_profile",
        "github_username",
        "portfolio_url",
    ]
)


VEHICLE_PROPERTY_PII = frozenset(
    [
        "vin",
        "vehicle_identification_number",
        "license_plate",
        "plate_number",
        "registration_number",
        "vehicle_registration",
        "car_registration",
        "vehicle_title",
        "title_number",
        "insurance_policy_auto",
        "auto_insurance",
        "drivers_license_number",
        "dl_number",
        "vehicle_make",
        "vehicle_model",
        "vehicle_year",
        "odometer_reading",
        "mileage",
        "property_deed",
        "deed_number",
        "parcel_number",
        "property_tax_id",
        "assessment_number",
        "mortgage_account",
        "loan_number",
        "escrow_number",
        "home_insurance",
        "property_insurance",
        "hoa_account",
        "homeowners_association",
        "utility_account",
        "electric_account",
        "gas_account",
        "water_account",
        "sewer_account",
        "trash_account",
        "cable_account",
        "internet_account",
        "alarm_code",
        "gate_code",
        "lockbox_code",
    ]
)


SENSITIVE_PREFERENCES = frozenset(
    [
        "race",
        "ethnicity",
        "nationality",
        "citizenship",
        "religion",
        "religious_affiliation",
        "faith",
        "political_affiliation",
        "political_party",
        "voting_record",
        "sexual_orientation",
        "gender_identity",
        "pronouns",
        "marital_status",
        "relationship_status",
        "domestic_partnership",
        "union_membership",
        "professional_association",
        "club_membership",
        "organization_membership",
        "charitable_donations",
        "political_donations",
        "philosophical_beliefs",
        "ethical_beliefs",
        "criminal_record",
        "arrest_record",
        "conviction",
        "court_case",
        "lawsuit",
        "bankruptcy",
        "divorce_decree",
        "custody_agreement",
        "military_service",
        "veteran_status",
        "discharge_type",
        "dietary_restrictions",
        "food_allergies",
        "dietary_preference",
        "smoking_status",
        "alcohol_consumption",
        "drug_use",
        "hobbies",
        "interests",
        "activities",
        "reading_history",
        "viewing_history",
        "purchase_history",
        "search_history",
        "browsing_history",
        "click_stream",
    ]
)


QUASI_IDENTIFIERS = frozenset(
    [
        "age",
        "birth_date",
        "date_of_birth",
        "dob",
        "birth_year",
        "gender",
        "sex",
        "male_female",
        "zip_code",
        "postal_code",
        "occupation",
        "job_title",
        "profession",
        "education_level",
        "degree",
        "school_name",
        "income_range",
        "income_bracket",
        "vehicle_type",
        "car_make",
        "car_model",
        "employment_status",
        "employer_name",
        "family_size",
        "number_of_children",
        "home_ownership",
        "property_type",
    ]
)


THIRD_PARTY_IDS = frozenset(
    [
        "google_analytics_id",
        "ga_client_id",
        "analytics_id",
        "mixpanel_distinct_id",
        "amplitude_user_id",
        "segment_id",
        "heap_user_id",
        "fullstory_id",
        "hotjar_id",
        "facebook_pixel_id",
        "fb_browser_id",
        "salesforce_id",
        "sfdc_contact_id",
        "lead_id",
        "hubspot_contact_id",
        "marketo_lead_id",
        "mailchimp_subscriber_id",
        "sendgrid_contact_id",
        "constant_contact_id",
        "campaign_monitor_id",
        "shopify_customer_id",
        "woocommerce_customer_id",
        "magento_customer_id",
        "bigcommerce_customer_id",
        "stripe_customer_id",
        "square_customer_id",
        "paypal_payer_id",
        "braintree_customer_id",
        "authorize_net_profile_id",
        "adyen_shopper_id",
        "zendesk_user_id",
        "intercom_user_id",
        "freshdesk_contact_id",
        "slack_user_id",
        "discord_user_id",
        "telegram_user_id",
        "whatsapp_phone",
        "signal_number",
        "zoom_user_id",
        "teams_user_id",
        "webex_id",
        "facebook_user_id",
        "instagram_handle",
        "twitter_handle",
        "linkedin_member_id",
        "youtube_channel_id",
        "tiktok_user_id",
        "snapchat_username",
        "pinterest_user_id",
        "reddit_username",
        "github_username",
        "gitlab_username",
        "bitbucket_username",
    ]
)


CONTACT_METHODS = frozenset(
    [
        "email",
        "email_address",
        "contact_email",
        "personal_email",
        "phone",
        "phone_number",
        "telephone",
        "tel",
        "mobile",
        "mobile_number",
        "cell",
        "cell_phone",
        "work_phone",
        "office_phone",
        "business_phone",
        "home_phone",
        "landline",
        "residential_phone",
        "fax",
        "fax_number",
        "facsimile",
        "pager",
        "beeper",
        "pager_number",
        "skype_id",
        "skype_name",
        "teams_id",
        "whatsapp",
        "whatsapp_number",
        "signal_number",
        "telegram_handle",
        "telegram_username",
        "wechat_id",
        "line_id",
        "viber_number",
        "emergency_contact",
        "next_of_kin",
        "ice_contact",
    ]
)


BEHAVIORAL_DATA = frozenset(
    [
        "browsing_history",
        "search_history",
        "click_history",
        "purchase_history",
        "transaction_history",
        "order_history",
        "viewing_history",
        "watch_history",
        "play_history",
        "download_history",
        "app_usage",
        "screen_time",
        "location_history",
        "travel_history",
        "places_visited",
        "call_log",
        "sms_history",
        "message_history",
        "contact_list",
        "address_book",
        "friend_list",
        "calendar_events",
        "appointments",
        "meetings",
        "fitness_data",
        "health_data",
        "sleep_data",
        "diet_log",
        "exercise_log",
        "workout_data",
        "mood_tracking",
        "journal_entries",
        "notes",
        "voice_recordings",
        "audio_messages",
        "voicemail",
        "photos",
        "videos",
        "screenshots",
        "recordings",
    ]
)


SANITIZED_TOKENS = frozenset(
    [
        "hash",
        "hashed",
        "encrypt",
        "encrypted",
        "mask",
        "masked",
        "redact",
        "redacted",
        "obfuscate",
        "obfuscated",
        "salt",
        "salted",
        "token",
        "jwt",
        "placeholder",
        "example",
        "dummy",
        "mock",
        "fake",
        "sample",
        "template",
        "check",
        "validate",
        "verify",
        "is",
        "has",
        "can",
        "should",
        "valid",
        "invalid",
        "enabled",
        "disabled",
        "len",
        "length",
        "size",
        "count",
        "index",
        "type",
        "format",
        "pattern",
        "regex",
        "schema",
        "btn",
        "button",
        "label",
        "input",
        "field",
        "form",
        "handler",
        "callback",
        "listener",
        "ref",
        "element",
    ]
)


LOGGING_FUNCTIONS = frozenset(
    [
        "print",
        "pprint",
        "logger.debug",
        "logger.info",
        "logger.warning",
        "logger.error",
        "logger.critical",
        "logging.debug",
        "logging.info",
        "logging.warning",
        "logging.error",
        "logging.critical",
        "log.debug",
        "log.info",
        "log.warning",
        "log.error",
        "log.critical",
        "console.log",
        "console.debug",
        "console.info",
        "console.warn",
        "console.error",
        "console.trace",
        "console.dir",
        "console.table",
        "console.group",
        "winston.debug",
        "winston.info",
        "winston.warn",
        "winston.error",
        "bunyan.debug",
        "bunyan.info",
        "bunyan.warn",
        "bunyan.error",
        "pino.debug",
        "pino.info",
        "pino.warn",
        "pino.error",
        "morgan",
        "debug",
        "error_log",
        "var_dump",
        "print_r",
        "var_export",
        "System.out.println",
        "System.err.println",
        "logger.trace",
        "logger.debug",
        "logger.info",
        "logger.warn",
        "logger.error",
        "Console.WriteLine",
        "Debug.WriteLine",
        "Trace.WriteLine",
        "puts",
        "p",
        "pp",
        "logger.debug",
        "Rails.logger",
    ]
)

ERROR_RESPONSE_FUNCTIONS = frozenset(
    [
        "Response",
        "HttpResponse",
        "JsonResponse",
        "render",
        "make_response",
        "jsonify",
        "send_error",
        "abort",
        "res.send",
        "res.json",
        "res.status",
        "res.render",
        "response.send",
        "response.json",
        "response.status",
        "ctx.body",
        "ctx.response",
        "reply.send",
        "reply.code",
        "response.getWriter",
        "response.getOutputStream",
        "echo",
        "print",
        "die",
        "exit",
        "json_encode",
        "render",
        "redirect_to",
        "respond_to",
    ]
)


DATABASE_STORAGE_FUNCTIONS = frozenset(
    [
        "execute",
        "executemany",
        "query",
        "insert",
        "update",
        "delete",
        "save",
        "create",
        "persist",
        "store",
        "write",
        "save",
        "create",
        "update",
        "bulk_create",
        "bulk_update",
        "findOneAndUpdate",
        "updateOne",
        "updateMany",
        "insertOne",
        "insertMany",
        "replaceOne",
        "put",
        "putItem",
        "set",
        "setItem",
        "add",
        "append",
        "hset",
        "hmset",
        "sadd",
        "zadd",
        "lpush",
        "rpush",
        "write",
        "writeFile",
        "writeFileSync",
        "appendFile",
        "fwrite",
        "file_put_contents",
        "save_to_file",
        "s3.upload",
        "s3.putObject",
        "blob.upload",
        "storage.save",
        "bucket.upload",
        "container.create_blob",
    ]
)

CLIENT_STORAGE_FUNCTIONS = frozenset(
    [
        "localStorage.setItem",
        "sessionStorage.setItem",
        "document.cookie",
        "setCookie",
        "cookies.set",
        "indexedDB.put",
        "cache.put",
        "store.set",
    ]
)


def get_applicable_regulations(pii_type: str) -> list[PrivacyRegulation]:
    """Map PII types to applicable privacy regulations."""
    regulations = []

    regulations.append(PrivacyRegulation.GDPR)

    if pii_type in US_GOVERNMENT_IDS or pii_type in FINANCIAL_PII:
        regulations.append(PrivacyRegulation.CCPA)

    if pii_type in CHILDREN_PII:
        regulations.append(PrivacyRegulation.COPPA)

    if pii_type in HEALTHCARE_PII:
        regulations.append(PrivacyRegulation.HIPAA)

    if pii_type in FINANCIAL_PII and any(
        card in pii_type.lower() for card in ["credit", "debit", "card", "cvv"]
    ):
        regulations.append(PrivacyRegulation.PCI_DSS)

    if pii_type in CHILDREN_PII and any(
        edu in pii_type.lower() for edu in ["student", "school", "education"]
    ):
        regulations.append(PrivacyRegulation.FERPA)

    if pii_type in BIOMETRIC_PII:
        regulations.append(PrivacyRegulation.BIPA)

    return regulations


def analyze(context: StandardRuleContext) -> RuleResult:
    """Detect PII exposure issues using comprehensive international patterns.

    Args:
        context: Provides db_path, file_path, content, language, project_path

    Returns:
        RuleResult with findings list and fidelity manifest
    """
    findings: list[StandardFinding] = []

    if not context.db_path:
        return RuleResult(findings=findings, manifest={})

    with RuleDB(context.db_path, METADATA.name) as db:
        pii_categories = _organize_pii_patterns()

        findings.extend(_detect_direct_pii(db, pii_categories))
        findings.extend(_detect_pii_in_logging(db, pii_categories))
        findings.extend(_detect_pii_in_errors(db, pii_categories))
        findings.extend(_detect_pii_in_urls(db, pii_categories))
        findings.extend(_detect_unencrypted_pii(db, pii_categories))
        findings.extend(_detect_client_side_pii(db, pii_categories))
        findings.extend(_detect_pii_in_exceptions(db, pii_categories))
        findings.extend(_detect_derived_pii(db, pii_categories))
        findings.extend(_detect_aggregated_pii(db))
        findings.extend(_detect_third_party_pii(db, pii_categories))
        findings.extend(_detect_pii_in_route_patterns(db, pii_categories))
        findings.extend(_detect_pii_in_apis(db, pii_categories))

        findings.extend(_detect_pii_in_exports(db, pii_categories))
        findings.extend(_detect_pii_retention(db, pii_categories))
        findings.extend(_detect_pii_cross_border(db, pii_categories))
        findings.extend(_detect_pii_consent_gaps(db, pii_categories))
        findings.extend(_detect_pii_in_metrics(db, pii_categories))
        findings.extend(_detect_pii_access_control(db, pii_categories))

        return RuleResult(findings=findings, manifest=db.get_manifest())


def _organize_pii_patterns() -> dict[str, set[str]]:
    """Organize PII patterns by category for efficient searching."""
    return {
        "government": US_GOVERNMENT_IDS | INTERNATIONAL_GOVERNMENT_IDS,
        "healthcare": HEALTHCARE_PII,
        "financial": FINANCIAL_PII,
        "children": CHILDREN_PII,
        "biometric": BIOMETRIC_PII,
        "digital": DIGITAL_IDENTITY_PII,
        "location": LOCATION_PII,
        "employment": EMPLOYMENT_PII,
        "vehicle_property": VEHICLE_PROPERTY_PII,
        "sensitive": SENSITIVE_PREFERENCES,
        "third_party": THIRD_PARTY_IDS,
        "contact": CONTACT_METHODS,
        "behavioral": BEHAVIORAL_DATA,
        "quasi": QUASI_IDENTIFIERS,
    }


_CAMEL_CASE_TOKEN_RE = re.compile(r"[A-Z]+(?=[A-Z][a-z]|[0-9]|$)|[A-Z]?[a-z]+|[0-9]+")


def _split_identifier_tokens(value: str | None) -> list[str]:
    """Split an identifier or arbitrary string into normalized tokens."""
    if not value:
        return []

    tokens: list[str] = []

    for chunk in re.split(r"[^0-9A-Za-z]+", value):
        if not chunk:
            continue
        tokens.extend(_CAMEL_CASE_TOKEN_RE.findall(chunk))

    return [token.lower() for token in tokens if token]


@lru_cache(maxsize=4096)
def _pattern_tokens(pattern: str) -> tuple[str, ...]:
    """Cached version of token splitting for PII patterns."""
    return tuple(_split_identifier_tokens(pattern))


def _match_pattern_tokens(tokens: set[str], pattern: str) -> bool:
    """Check if identifier tokens match a PII pattern."""
    pattern_tokens = _pattern_tokens(pattern)
    if not pattern_tokens:
        return False
    if len(pattern_tokens) == 1:
        return pattern_tokens[0] in tokens
    return all(token in tokens for token in pattern_tokens)


def _detect_pii_matches(
    text: str | None, pii_categories: dict[str, set[str]]
) -> list[tuple[str, str]]:
    """Detect PII patterns in text using token-based matching."""
    tokens = set(_split_identifier_tokens(text))
    if not tokens:
        return []

    matches: list[tuple[str, str]] = []

    for category, patterns in pii_categories.items():
        for pattern in patterns:
            if _match_pattern_tokens(tokens, pattern):
                matches.append((pattern, category))

    return matches


def _detect_specific_pattern(text: str | None, patterns: set[str]) -> str | None:
    """Detect if text matches any pattern from a specific set."""
    tokens = set(_split_identifier_tokens(text))
    if not tokens:
        return None

    for pattern in patterns:
        if _match_pattern_tokens(tokens, pattern):
            return pattern

    return None


def _is_sanitized(tokens: set[str]) -> bool:
    """Check if tokens indicate sanitized/safe context (not raw PII).

    Returns True if variable name suggests:
    - Data is encrypted/hashed/masked
    - It's a boolean check, not data storage
    - It's a UI element reference
    - It's a placeholder/mock value
    """
    return not tokens.isdisjoint(SANITIZED_TOKENS)


def _is_test_file(file_path: str) -> bool:
    """Check if file is a test/mock file where PII is expected."""
    path_lower = file_path.lower()
    test_indicators = [
        "/test/",
        "/tests/",
        "/__tests__/",
        "/spec/",
        "/mock/",
        "/mocks/",
        "/fixture/",
        "/fixtures/",
        ".test.",
        ".spec.",
        "_test.",
        "_spec.",
        "test_",
        "spec_",
    ]
    return any(indicator in path_lower for indicator in test_indicators)


def _determine_confidence(
    pii_type: str, context: str, is_encrypted: bool = False, is_test_file: bool = False
) -> Confidence:
    """Determine confidence level based on PII type and context."""

    if is_test_file:
        return Confidence.LOW

    if is_encrypted:
        return Confidence.MEDIUM

    critical_patterns = {
        "ssn",
        "credit_card",
        "password",
        "api_key",
        "private_key",
        "passport",
        "drivers_license",
        "bank_account",
        "medical_record",
    }
    if any(pattern in pii_type.lower() for pattern in critical_patterns):
        return Confidence.HIGH

    if "log" in context.lower() or "error" in context.lower():
        return Confidence.HIGH

    return Confidence.MEDIUM


def _detect_direct_pii(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect direct PII fields in assignments using token-based matching.

    Uses token matching (not substring) to avoid false positives like:
    - 'finalResult' matching 'fin' (Finnish ID)
    - 'companyId' matching 'pan' (Primary Account Number)

    Skips variables with sanitization indicators like:
    - password_hash, encrypted_ssn, masked_credit_card
    - is_email_valid, has_phone, check_ssn
    """
    findings = []

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, var, _expr in rows:
        var_tokens = set(_split_identifier_tokens(var))
        if not var_tokens:
            continue

        if _is_sanitized(var_tokens):
            continue

        is_test = _is_test_file(file)

        pii_category = None
        pii_pattern = None

        for category, patterns in pii_categories.items():
            for pattern in patterns:
                if _match_pattern_tokens(var_tokens, pattern):
                    pii_category = category
                    pii_pattern = pattern
                    break
            if pii_category:
                break

        if pii_category:
            regulations = get_applicable_regulations(pii_pattern)

            confidence = (
                Confidence.LOW if is_test else _determine_confidence(pii_pattern, "assignment")
            )

            findings.append(
                StandardFinding(
                    rule_name=f"pii-direct-{pii_category}",
                    message=f"Direct PII assignment: {var} ({pii_category})",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=confidence,
                    category="privacy",
                    snippet=f"{var} = ...",
                    cwe_id="CWE-359",
                    additional_info={
                        "regulations": [r.value for r in regulations],
                        "pii_category": pii_category,
                    },
                )
            )

    return findings


def _detect_pii_in_logging(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII being logged."""
    findings = []

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(log_func in func for log_func in LOGGING_FUNCTIONS):
            continue

        if not args:
            continue

        detected_pii = _detect_pii_matches(args, pii_categories)

        if detected_pii:
            pii_pattern, _pii_category = detected_pii[0]
            regulations = get_applicable_regulations(pii_pattern)

            findings.append(
                StandardFinding(
                    rule_name="pii-logged",
                    message=f"PII logged: {', '.join([p[0] for p in detected_pii[:3]])}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=_determine_confidence(pii_pattern, "logging"),
                    category="privacy",
                    snippet=f"{func}({pii_pattern}...)",
                    cwe_id="CWE-532",
                    additional_info={
                        "regulations": [r.value for r in regulations],
                        "pii_types": [p[0] for p in detected_pii],
                        "pii_categories": list({p[1] for p in detected_pii}),
                    },
                )
            )

    return findings


def _detect_pii_in_errors(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII in error responses.

    Pre-fetches symbol data to avoid N+1 queries.
    """
    findings = []

    catch_symbols = db.query(
        Q("symbols").select("path", "line").where("type = ?", "catch").order_by("path, line")
    )
    catch_by_file: dict[str, list[int]] = {}
    for path, line in catch_symbols:
        if path not in catch_by_file:
            catch_by_file[path] = []
        catch_by_file[path].append(line)

    error_symbols = db.query(
        Q("symbols").select("path", "line", "name").where("name IS NOT NULL").order_by("path, line")
    )
    error_names_by_file: dict[str, list[int]] = {}
    for path, line, name in error_symbols:
        if name and ("error" in name.lower() or "exception" in name.lower()):
            if path not in error_names_by_file:
                error_names_by_file[path] = []
            error_names_by_file[path].append(line)

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(resp_func in func for resp_func in ERROR_RESPONSE_FUNCTIONS):
            continue

        catch_count = sum(1 for c_line in catch_by_file.get(file, []) if abs(c_line - line) <= 10)

        error_count = sum(
            1 for e_line in error_names_by_file.get(file, []) if abs(e_line - line) <= 10
        )

        in_error_context = catch_count > 0 or error_count > 0

        if in_error_context:
            detected_pii = _detect_pii_matches(args, pii_categories)

            if detected_pii:
                pii_pattern, _pii_category = detected_pii[0]
                regulations = get_applicable_regulations(pii_pattern)

                findings.append(
                    StandardFinding(
                        rule_name="pii-error-response",
                        message=f"PII in error response: {pii_pattern}",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="privacy",
                        snippet=f"{func}({{error: ...{pii_pattern}...}})",
                        cwe_id="CWE-209",
                        additional_info={"regulations": [r.value for r in regulations]},
                    )
                )

    return findings


def _detect_pii_in_urls(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII in URLs and query parameters."""
    findings = []

    url_functions = frozenset(["urlencode", "encodeURIComponent", "URLSearchParams", "build_url"])

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(url_func in func for url_func in url_functions):
            continue

        critical_url_pii = {
            "password",
            "ssn",
            "credit_card",
            "api_key",
            "token",
            "bank_account",
            "passport",
            "drivers_license",
        }

        matched = _detect_specific_pattern(args, critical_url_pii)
        if matched:
            findings.append(
                StandardFinding(
                    rule_name="pii-in-url",
                    message=f"Critical PII in URL: {matched}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category="privacy",
                    snippet=f"{func}(...{matched}=...)",
                    cwe_id="CWE-598",
                    additional_info={
                        "regulations": [PrivacyRegulation.GDPR.value, PrivacyRegulation.CCPA.value]
                    },
                )
            )

    return findings


def _detect_unencrypted_pii(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect unencrypted PII being stored.

    Pre-fetches encryption calls to avoid N+1 queries.
    """
    findings = []

    must_encrypt = {
        "ssn",
        "credit_card",
        "bank_account",
        "passport",
        "drivers_license",
        "medical_record",
        "tax_id",
        "biometric",
        "password",
    }

    all_calls = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    encrypt_by_file: dict[str, list[int]] = {}
    storage_candidates: list[tuple[str, int, str, str]] = []

    for file, line, func, args in all_calls:
        func_lower = func.lower() if func else ""

        if "encrypt" in func_lower or "hash" in func_lower or "bcrypt" in func_lower:
            if file not in encrypt_by_file:
                encrypt_by_file[file] = []
            encrypt_by_file[file].append(line)

        if args and any(store_func in func for store_func in DATABASE_STORAGE_FUNCTIONS):
            storage_candidates.append((file, line, func, args))

    for file, line, func, args in storage_candidates:
        matched = _detect_specific_pattern(args, must_encrypt)
        if matched:
            has_encryption = any(
                abs(e_line - line) <= 5 for e_line in encrypt_by_file.get(file, [])
            )

            if not has_encryption:
                findings.append(
                    StandardFinding(
                        rule_name="pii-unencrypted-storage",
                        message=f"Unencrypted {matched} being stored",
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category="privacy",
                        snippet=f"{func}(...{matched}...)",
                        cwe_id="CWE-311",
                        additional_info={
                            "regulations": [
                                PrivacyRegulation.GDPR.value,
                                PrivacyRegulation.PCI_DSS.value,
                            ]
                        },
                    )
                )

    return findings


def _detect_client_side_pii(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII stored in client-side storage."""
    findings = []

    forbidden_client_pii = {
        "password",
        "ssn",
        "credit_card",
        "cvv",
        "bank_account",
        "api_key",
        "private_key",
        "passport",
        "drivers_license",
    }

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(storage_func in func for storage_func in CLIENT_STORAGE_FUNCTIONS):
            continue

        args_tokens = set(_split_identifier_tokens(args))
        if not args_tokens:
            continue

        if _is_sanitized(args_tokens):
            continue

        matched_pii = _detect_specific_pattern(args, forbidden_client_pii)
        if matched_pii:
            findings.append(
                StandardFinding(
                    rule_name="pii-client-storage",
                    message=f"Sensitive PII in browser storage: {matched_pii}",
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category="privacy",
                    snippet=f'{func}("{matched_pii}", ...)',
                    cwe_id="CWE-922",
                    additional_info={
                        "regulations": [
                            PrivacyRegulation.GDPR.value,
                            PrivacyRegulation.PCI_DSS.value,
                        ],
                        "storage_type": "localStorage"
                        if "localStorage" in func
                        else "sessionStorage"
                        if "sessionStorage" in func
                        else "cookie",
                    },
                )
            )

    return findings


def _detect_pii_in_exceptions(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII exposed in exception handling.

    Pre-fetches function calls to avoid N+1 queries.
    """
    findings = []

    handler_rows = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type IN ('catch', 'except', 'exception', 'error')")
        .order_by("path, line")
    )

    handler_files = {row[0] for row in handler_rows}
    if not handler_files:
        return findings

    all_calls = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    calls_by_file: dict[str, list[tuple[int, str, str]]] = {}
    for file, line, func, args in all_calls:
        if file in handler_files:
            if file not in calls_by_file:
                calls_by_file[file] = []
            calls_by_file[file].append((line, func, args))

    log_keywords = frozenset(["log", "print", "send"])

    for file, handler_line, _handler_name in handler_rows:
        file_calls = calls_by_file.get(file, [])

        for call_line, func, args in file_calls:
            if not (handler_line <= call_line <= handler_line + 20):
                continue

            if not any(keyword in func.lower() for keyword in log_keywords):
                continue

            args_lower = args.lower()
            if any(
                exc in args_lower for exc in ["exception", "error", "err", "exc", "stack", "trace"]
            ):
                findings.append(
                    StandardFinding(
                        rule_name="pii-exception-exposure",
                        message="Exception details may contain PII",
                        file_path=file,
                        line=call_line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        category="privacy",
                        snippet=f"{func}(exception)",
                        cwe_id="CWE-209",
                    )
                )

    return findings


def _detect_derived_pii(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII derived from other fields."""
    findings = []

    derived_patterns = [
        ("full_name", ["first_name", "last_name"]),
        ("complete_address", ["street", "city", "state", "zip"]),
        ("age", ["birth_date", "dob"]),
        ("account_info", ["account_number", "routing_number"]),
    ]

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("target_var IS NOT NULL")
        .where("source_expr IS NOT NULL")
    )

    for file, line, var, expr in rows:
        var_lower = var.lower()
        expr_lower = expr.lower()

        for derived_field, source_fields in derived_patterns:
            if derived_field not in var_lower:
                continue

            if all(sf in expr_lower for sf in source_fields):
                findings.append(
                    StandardFinding(
                        rule_name="pii-derived",
                        message=f"Derived PII created: {var} from {', '.join(source_fields)}",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.MEDIUM,
                        category="privacy",
                        snippet=f"{var} = ...{source_fields[0]}...{source_fields[-1]}...",
                        cwe_id="CWE-359",
                    )
                )
                break

    return findings


def _detect_aggregated_pii(db: RuleDB) -> list[StandardFinding]:
    """Detect quasi-identifiers that become PII when combined.

    Uses token-based matching to avoid false positives.
    Skips test files and sanitized variable names.
    """
    findings = []

    rows = db.query(
        Q("assignments").select("file", "line", "target_var").where("target_var IS NOT NULL")
    )

    file_quasi: dict[str, dict] = {}
    for file, line, var in rows:
        if _is_test_file(file):
            continue

        var_tokens = set(_split_identifier_tokens(var))
        if not var_tokens:
            continue

        if _is_sanitized(var_tokens):
            continue

        matched_quasi = _detect_specific_pattern(var, QUASI_IDENTIFIERS)
        if matched_quasi:
            if file not in file_quasi:
                file_quasi[file] = {"line": line, "count": 0, "vars": set()}
            file_quasi[file]["count"] += 1
            file_quasi[file]["vars"].add(var)
            if line < file_quasi[file]["line"]:
                file_quasi[file]["line"] = line

    for file, data in file_quasi.items():
        if data["count"] >= 3:
            findings.append(
                StandardFinding(
                    rule_name="pii-quasi-identifiers",
                    message=f"Multiple quasi-identifiers detected ({data['count']} fields)",
                    file_path=file,
                    line=data["line"],
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    category="privacy",
                    snippet="Multiple fields: age, zipcode, gender...",
                    cwe_id="CWE-359",
                    additional_info={
                        "note": "Combination of 3+ quasi-identifiers can identify individuals with 87% accuracy"
                    },
                )
            )

    return findings


def _detect_third_party_pii(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII being sent to third-party services."""
    findings = []

    third_party_apis = frozenset(
        [
            "analytics.track",
            "ga.send",
            "gtag",
            "mixpanel.track",
            "amplitude.track",
            "facebook.pixel",
            "fbq.track",
            "segment.track",
            "heap.track",
        ]
    )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(api in func for api in third_party_apis):
            continue

        if _is_test_file(file):
            continue

        args_tokens = set(_split_identifier_tokens(args))
        if not args_tokens:
            continue

        if _is_sanitized(args_tokens):
            continue

        detected_pii = _detect_pii_matches(args, pii_categories)

        if detected_pii:
            findings.append(
                StandardFinding(
                    rule_name="pii-third-party",
                    message=f"PII sent to third-party: {', '.join([p[0] for p in detected_pii[:3]])}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category="privacy",
                    snippet=f"{func}(...{detected_pii[0][0]}...)",
                    cwe_id="CWE-359",
                    additional_info={
                        "regulations": [PrivacyRegulation.GDPR.value, PrivacyRegulation.CCPA.value],
                        "note": "Third-party data sharing may require explicit consent",
                    },
                )
            )

    return findings


def register_taint_patterns(taint_registry):
    """Register PII patterns with taint analyzer for flow tracking."""

    all_pii = set()
    for patterns in [
        US_GOVERNMENT_IDS,
        INTERNATIONAL_GOVERNMENT_IDS,
        HEALTHCARE_PII,
        FINANCIAL_PII,
        CHILDREN_PII,
        BIOMETRIC_PII,
        DIGITAL_IDENTITY_PII,
        LOCATION_PII,
        EMPLOYMENT_PII,
        VEHICLE_PROPERTY_PII,
    ]:
        all_pii.update(patterns)

    for pattern in all_pii:
        taint_registry.register_source(pattern, "pii", "any")

    for func in LOGGING_FUNCTIONS:
        taint_registry.register_sink(func, "logging", "any")

    for func in ERROR_RESPONSE_FUNCTIONS:
        taint_registry.register_sink(func, "error_response", "any")

    for func in CLIENT_STORAGE_FUNCTIONS:
        taint_registry.register_sink(func, "client_storage", "any")


def _detect_pii_in_route_patterns(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detects PII exposed in parameterized API route patterns."""
    findings = []

    all_pii_patterns = set()
    for category_patterns in pii_categories.values():
        all_pii_patterns.update(category_patterns)

    rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "pattern")
        .where("pattern IS NOT NULL")
        .where("pattern != ''")
        .order_by("file, line")
    )

    for file, line, method, route_pattern in rows:
        extracted_params = []

        for segment in route_pattern.split("/"):
            if segment.startswith(":"):
                param_name = segment[1:]

                param_name = param_name.split("?")[0].split("#")[0]
                if param_name:
                    extracted_params.append(param_name)

            elif segment.startswith("{") and segment.endswith("}"):
                param_name = segment[1:-1]
                if param_name:
                    extracted_params.append(param_name)

        for param_name in extracted_params:
            normalized_param = param_name.lower().replace("_", "").replace("-", "")

            for pii_pattern in all_pii_patterns:
                normalized_pii = pii_pattern.lower().replace("_", "").replace("-", "")

                if normalized_pii == normalized_param:
                    findings.append(
                        StandardFinding(
                            rule_name="pii-in-route-parameter",
                            message=f'PII parameter "{param_name}" exposed in API route',
                            file_path=file,
                            line=line,
                            severity=Severity.HIGH,
                            category="privacy",
                            confidence=Confidence.MEDIUM,
                            snippet=f"{method.upper()} {route_pattern}",
                            cwe_id="CWE-598",
                        )
                    )
                    break

    return findings


def _detect_pii_in_apis(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII exposed in API endpoints."""
    findings = []

    rows = db.query(
        Q("api_endpoints")
        .select("file", "line", "method", "path")
        .where("path IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, method, route_path in rows:
        detected_pii = _detect_pii_matches(route_path, pii_categories)

        if detected_pii:
            pii_pattern, pii_category = detected_pii[0]
            regulations = get_applicable_regulations(pii_pattern)

            if method.upper() == "GET":
                severity = Severity.CRITICAL
                confidence = Confidence.HIGH
            else:
                severity = Severity.HIGH
                confidence = Confidence.MEDIUM

            findings.append(
                StandardFinding(
                    rule_name="pii-api-exposure",
                    message=f"PII exposed in API: {pii_pattern} via {method}",
                    file_path=file,
                    line=line,
                    severity=severity,
                    confidence=confidence,
                    category="privacy",
                    snippet=f"{method} {route_path} [{pii_pattern}]",
                    cwe_id="CWE-598",
                    additional_info={
                        "regulations": [r.value for r in regulations],
                        "method": method,
                        "pii_category": pii_category,
                    },
                )
            )

    return findings


def _detect_pii_in_exports(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII in data exports (CSV, JSON, XML)."""
    findings = []

    export_functions = frozenset(
        [
            "to_csv",
            "to_json",
            "to_xml",
            "to_excel",
            "export",
            "download",
            "generate_report",
            "writeFile",
            "fs.writeFile",
            "fs.writeFileSync",
            "json.dump",
            "json.dumps",
            "JSON.stringify",
            "csv.writer",
            "csv.DictWriter",
        ]
    )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(export_func in func for export_func in export_functions):
            continue

        args_lower = args.lower()
        pii_count = 0
        detected_types = []
        for _category, patterns in pii_categories.items():
            for pattern in patterns:
                if pattern in args_lower:
                    pii_count += 1
                    detected_types.append(pattern)

        if pii_count >= 2:
            findings.append(
                StandardFinding(
                    rule_name="pii-bulk-export",
                    message=f"Bulk PII export detected: {', '.join(detected_types[:3])}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category="privacy",
                    snippet=f"{func}([...{pii_count} PII fields...])",
                    cwe_id="CWE-359",
                    additional_info={
                        "regulations": [PrivacyRegulation.GDPR.value],
                        "pii_count": pii_count,
                        "note": "GDPR requires data minimization and purpose limitation",
                    },
                )
            )

    return findings


def _detect_pii_retention(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII retention policy violations.

    Uses token-based matching to avoid false positives.
    Only flags high-sensitivity PII categories without TTL.
    """
    findings = []

    cache_functions = frozenset(
        [
            "cache.set",
            "redis.set",
            "memcached.set",
            "localStorage.setItem",
            "sessionStorage.setItem",
        ]
    )

    sensitive_categories = {"government", "healthcare", "financial", "children"}

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(cache_func in func for cache_func in cache_functions):
            continue

        if _is_test_file(file):
            continue

        args_tokens = set(_split_identifier_tokens(args))
        if not args_tokens:
            continue

        if _is_sanitized(args_tokens):
            continue

        has_pii = False
        for category, patterns in pii_categories.items():
            if category not in sensitive_categories:
                continue
            for pattern in patterns:
                if _match_pattern_tokens(args_tokens, pattern):
                    has_pii = True
                    break
            if has_pii:
                break

        if has_pii:
            ttl_keywords = {"ttl", "expire", "expires", "timeout", "maxage", "max_age"}
            has_ttl = not args_tokens.isdisjoint(ttl_keywords)

            if not has_ttl:
                findings.append(
                    StandardFinding(
                        rule_name="pii-retention-violation",
                        message="PII cached without retention policy (no TTL)",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.MEDIUM,
                        category="privacy",
                        snippet=f"{func}(pii_data) // No TTL",
                        cwe_id="CWE-359",
                        additional_info={
                            "regulations": [PrivacyRegulation.GDPR.value],
                            "note": "GDPR Article 5(1)(e): Data retention limitation principle",
                        },
                    )
                )

    return findings


def _detect_pii_cross_border(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect cross-border PII transfers.

    Pre-fetches function call args to avoid N+1 queries.
    """
    findings = []

    cross_border_apis = frozenset(
        [
            "aws-",
            "s3-",
            "cloudfront",
            "azure-",
            "blob.core",
            "googleapis.com",
            "gstatic.com",
            "alibabacloud",
            "aliyun",
            "cdn.",
            "cloudflare",
            ".eu-",
            ".us-",
            ".ap-",
            ".cn-",
        ]
    )

    all_args = db.query(
        Q("function_call_args")
        .select("file", "line", "argument_expr")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    args_by_file: dict[str, list[tuple[int, str]]] = {}
    for file, line, arg in all_args:
        if file not in args_by_file:
            args_by_file[file] = []
        args_by_file[file].append((line, arg))

    rows = db.query(
        Q("assignments")
        .select("file", "line", "target_var", "source_expr")
        .where("source_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, var, expr in rows:
        expr_lower = expr.lower()
        if not ("http" in expr_lower or "api" in expr_lower):
            continue

        is_cross_border = any(api in expr_lower for api in cross_border_apis)

        if is_cross_border:
            has_var_usage = any(
                var in arg
                for arg_line, arg in args_by_file.get(file, [])
                if abs(arg_line - line) <= 10
            )

            if has_var_usage:
                findings.append(
                    StandardFinding(
                        rule_name="pii-cross-border",
                        message="Potential cross-border PII transfer detected",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.LOW,
                        category="privacy",
                        snippet=f"{var} = {expr[:50]}...",
                        cwe_id="CWE-359",
                        additional_info={
                            "regulations": [PrivacyRegulation.GDPR.value],
                            "note": "GDPR Chapter V requires safeguards for international transfers",
                        },
                    )
                )

    return findings


def _detect_pii_consent_gaps(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII processing without consent checks.

    Pre-fetches all function calls to avoid N+1 queries.
    """
    findings = []

    consent_checks = frozenset(
        [
            "hasConsent",
            "checkConsent",
            "verifyConsent",
            "isOptedIn",
            "hasPermission",
            "canProcess",
            "gdprConsent",
            "cookieConsent",
            "privacyConsent",
        ]
    )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    funcs_by_file: dict[str, list[tuple[int, str]]] = {}
    processing_candidates: list[tuple[str, int, str, str]] = []

    processing_keywords = frozenset(["process", "analyze", "track", "collect"])

    for file, line, func, args in rows:
        func_lower = func.lower() if func else ""

        if file not in funcs_by_file:
            funcs_by_file[file] = []
        funcs_by_file[file].append((line, func_lower))

        if args and any(keyword in func_lower for keyword in processing_keywords):
            processing_candidates.append((file, line, func, args))

    for file, line, func, args in processing_candidates:
        args_lower = args.lower()
        has_pii = any(
            pattern in args_lower for patterns in pii_categories.values() for pattern in patterns
        )

        if has_pii:
            has_consent_check = any(
                any(consent in nearby_func for consent in consent_checks)
                for nearby_line, nearby_func in funcs_by_file.get(file, [])
                if abs(nearby_line - line) <= 20
            )

            if not has_consent_check:
                findings.append(
                    StandardFinding(
                        rule_name="pii-no-consent",
                        message="PII processing without apparent consent check",
                        file_path=file,
                        line=line,
                        severity=Severity.MEDIUM,
                        confidence=Confidence.LOW,
                        category="privacy",
                        snippet=f"{func}(pii_data)",
                        cwe_id="CWE-359",
                        additional_info={
                            "regulations": [
                                PrivacyRegulation.GDPR.value,
                                PrivacyRegulation.CCPA.value,
                            ],
                            "note": "GDPR requires explicit consent for data processing",
                        },
                    )
                )

    return findings


def _detect_pii_in_metrics(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII in metrics and monitoring."""
    findings = []

    metrics_functions = frozenset(
        [
            "statsd.",
            "prometheus.",
            "metrics.",
            "newrelic.",
            "datadog.",
            "grafana.",
            "telemetry.",
            "monitoring.",
            "apm.",
            "counter.increment",
            "gauge.set",
            "histogram.observe",
        ]
    )

    rows = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function", "argument_expr")
        .where("callee_function IS NOT NULL")
        .where("argument_expr IS NOT NULL")
        .order_by("file, line")
    )

    for file, line, func, args in rows:
        if not any(metric_func in func for metric_func in metrics_functions):
            continue

        forbidden_metrics_pii = {"email", "phone", "ssn", "password", "credit_card", "ip_address"}

        args_lower = args.lower()
        for pii in forbidden_metrics_pii:
            if pii in args_lower:
                findings.append(
                    StandardFinding(
                        rule_name="pii-in-metrics",
                        message=f"PII in metrics/monitoring: {pii}",
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        confidence=Confidence.HIGH,
                        category="privacy",
                        snippet=f"{func}(...{pii}...)",
                        cwe_id="CWE-359",
                        additional_info={
                            "note": "Metrics systems often have weak access controls and long retention"
                        },
                    )
                )

    return findings


def _detect_pii_access_control(db: RuleDB, pii_categories: dict) -> list[StandardFinding]:
    """Detect PII access without proper authorization checks.

    Pre-fetches function calls to avoid N+1 queries.
    """
    findings = []

    auth_checks = frozenset(
        [
            "isAuthorized",
            "hasRole",
            "hasPermission",
            "canAccess",
            "requireAuth",
            "checkAuth",
            "verifyAccess",
            "@authorized",
            "authenticate",
            "authorize",
            "@RequireRole",
            "@Secured",
        ]
    )

    rows = db.query(
        Q("symbols")
        .select("path", "line", "name")
        .where("type = ?", "function")
        .where("name IS NOT NULL")
        .order_by("path, line")
    )

    pii_function_keywords = frozenset(["get", "fetch", "load", "retrieve"])
    pii_entity_keywords = frozenset(["user", "profile", "customer", "patient"])

    candidates: list[tuple[str, int, str]] = []
    candidate_files: set[str] = set()

    for file, line, func_name in rows:
        func_name_lower = func_name.lower()
        has_pii_action = any(keyword in func_name_lower for keyword in pii_function_keywords)
        has_pii_entity = any(keyword in func_name_lower for keyword in pii_entity_keywords)

        if has_pii_action and has_pii_entity:
            candidates.append((file, line, func_name))
            candidate_files.add(file)

    if not candidates:
        return findings

    all_calls = db.query(
        Q("function_call_args")
        .select("file", "line", "callee_function")
        .where("callee_function IS NOT NULL")
        .order_by("file, line")
    )

    calls_by_file: dict[str, list[tuple[int, str]]] = {}
    for file, line, func in all_calls:
        if file in candidate_files:
            if file not in calls_by_file:
                calls_by_file[file] = []
            calls_by_file[file].append((line, func.lower() if func else ""))

    for file, line, func_name in candidates:
        has_auth = any(
            any(auth in call_func for auth in auth_checks)
            for call_line, call_func in calls_by_file.get(file, [])
            if line <= call_line <= line + 50
        )

        if not has_auth:
            findings.append(
                StandardFinding(
                    rule_name="pii-no-auth",
                    message=f"PII access without authorization check: {func_name}",
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    category="privacy",
                    snippet=f"function {func_name}() {{ /* No auth check */ }}",
                    cwe_id="CWE-862",
                    additional_info={
                        "regulations": [PrivacyRegulation.GDPR.value, PrivacyRegulation.HIPAA.value]
                    },
                )
            )

    return findings


__all__ = [
    "analyze",
    "METADATA",
    "register_taint_patterns",
    "PrivacyRegulation",
    "get_applicable_regulations",
]
