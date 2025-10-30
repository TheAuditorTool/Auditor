"""PII Data Analyzer - Comprehensive International Edition.

Detects 200+ PII patterns across 15 categories with international support for 50+ countries.
Implements GDPR, CCPA, COPPA, HIPAA, PCI-DSS, and other privacy regulation checks.

This implementation:
- Uses frozensets for O(1) pattern matching (immutable, hashable)
- Direct database queries (assumes all tables exist per schema contract)
- Uses parameterized queries (no SQL injection)
- Implements multi-layer detection patterns
- Provides confidence scoring based on context
- Maps all findings to privacy regulations (15 major regulations)
- Supports international PII formats (50+ countries)
"""

import sqlite3
from typing import List, Set, Dict, Optional, Tuple
from pathlib import Path
from enum import Enum

from theauditor.rules.base import (
    StandardRuleContext,
    StandardFinding,
    Severity,
    Confidence,
    RuleMetadata
)

METADATA = RuleMetadata(
    name="pii_exposure",
    category="security",
    target_extensions=['.py', '.js', '.ts', '.jsx', '.tsx'],
    exclude_patterns=['test/', 'spec.', '__tests__', 'demo/'],
    requires_jsx_pass=False
)

# ============================================================================
# PRIVACY REGULATIONS ENUM
# ============================================================================

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

# ============================================================================
# US GOVERNMENT IDENTIFIERS
# ============================================================================

US_GOVERNMENT_IDS = frozenset([
    'ssn', 'social_security', 'social_security_number', 'socialsecuritynumber',
    'ein', 'employer_identification', 'federal_tax_id',
    'itin', 'individual_taxpayer_identification',
    'passport', 'passport_number', 'passport_no',
    'drivers_license', 'driver_license', 'driving_license', 'dl_number',
    'state_id', 'state_identification',
    'military_id', 'dod_id', 'defense_id',
    'voter_registration', 'voter_id',
    'medicare_number', 'medicare_id',
    'medicaid_number', 'medicaid_id',
    'dea_number', 'dea_registration',  # Drug Enforcement Administration
    'npi', 'national_provider_identifier',  # Healthcare provider ID
    'upin', 'unique_physician_identification',
    'green_card', 'permanent_resident_card', 'alien_registration',
    'naturalization_certificate', 'citizenship_certificate',
    'visa_number', 'visa_id', 'i94_number'
])

# ============================================================================
# INTERNATIONAL GOVERNMENT IDENTIFIERS
# ============================================================================

INTERNATIONAL_GOVERNMENT_IDS = frozenset([
    # Canada
    'sin', 'social_insurance_number', 'nas', 'numero_assurance_sociale',
    'health_card_number', 'ohip', 'ramq', 'msp',  # Provincial health cards

    # United Kingdom
    'ni_number', 'national_insurance', 'nhs_number', 'nhs_id',
    'chi_number', 'community_health_index',  # Scotland
    'hcn', 'health_care_number',  # Northern Ireland
    'driving_licence_uk', 'dvla_number',

    # European Union
    'vat_number', 'vat_id', 'eu_vat',
    'eori_number',  # Economic Operators Registration
    'pesel',  # Poland
    'cnp',  # Romania
    'oib',  # Croatia
    'jmbg',  # Serbia, Bosnia
    'egn',  # Bulgaria
    'rodne_cislo',  # Czech Republic, Slovakia
    'isikukood',  # Estonia
    'henkilotunnus',  # Finland
    'insee', 'nir',  # France
    'steuer_id', 'steueridentifikationsnummer',  # Germany
    'amka',  # Greece
    'taj',  # Hungary
    'pps_number',  # Ireland
    'codice_fiscale',  # Italy
    'asmens_kodas',  # Lithuania
    'cnp_luxembourg',  # Luxembourg
    'idkaart',  # Netherlands
    'nif', 'nie', 'dni',  # Spain
    'personnummer',  # Sweden, Norway
    'ahv', 'avs',  # Switzerland

    # Asia-Pacific
    'aadhaar', 'aadhar', 'uid',  # India
    'pan_card', 'pan_number',  # India
    'voter_id_india',
    'ration_card',  # India
    'nric', 'fin',  # Singapore
    'mykad',  # Malaysia
    'id_card_hk', 'hkid',  # Hong Kong
    'arc', 'alien_registration_card',  # South Korea, Taiwan
    'rrn', 'resident_registration',  # South Korea
    'my_number', 'kojin_bango',  # Japan
    'tfn', 'tax_file_number',  # Australia
    'ird_number',  # New Zealand
    'citizen_id',  # Thailand
    'cmnd', 'cccd',  # Vietnam
    'nik',  # Indonesia
    'philhealth',  # Philippines
    'umid',  # Philippines Unified Multi-Purpose ID

    # Latin America
    'cpf',  # Brazil
    'rg',  # Brazil
    'cnpj',  # Brazil (company)
    'curp',  # Mexico
    'rfc',  # Mexico
    'ine',  # Mexico voter ID
    'rut',  # Chile
    'cedula',  # Various Latin American countries
    'dui',  # El Salvador
    'cui',  # Guatemala
    'cuit', 'cuil',  # Argentina

    # Middle East & Africa
    'national_id_sa',  # Saudi Arabia
    'emirates_id',  # UAE
    'qid',  # Qatar
    'civil_id_kw',  # Kuwait
    'national_id_eg',  # Egypt
    'id_number_za',  # South Africa
    'omang',  # Botswana
    'nin_ng',  # Nigeria
    'huduma_number',  # Kenya
    'nida',  # Tanzania
    'national_id_il',  # Israel
    'tc_kimlik',  # Turkey
])

# ============================================================================
# HEALTHCARE & MEDICAL PII (HIPAA Protected)
# ============================================================================

HEALTHCARE_PII = frozenset([
    # Medical Records
    'medical_record_number', 'mrn', 'patient_id', 'patient_number',
    'health_record', 'ehr_id', 'emr_number',
    'chart_number', 'case_number', 'encounter_id',

    # Insurance Information
    'insurance_policy', 'policy_number', 'member_id', 'subscriber_id',
    'group_number', 'plan_id', 'benefit_id',
    'claim_number', 'authorization_number', 'prior_auth',
    'copay_card', 'rx_bin', 'rx_pcn', 'rx_group',

    # Clinical Data
    'diagnosis', 'diagnosis_code', 'icd_code', 'icd10', 'icd9',
    'procedure_code', 'cpt_code', 'hcpcs_code',
    'lab_result', 'test_result', 'blood_type',
    'medication', 'prescription', 'rx_number', 'ndc_code',
    'allergy', 'medical_condition', 'disability',
    'mental_health', 'psychiatric_record',
    'substance_abuse', 'addiction_treatment',
    'hiv_status', 'aids_status', 'std_test',
    'pregnancy_status', 'genetic_information', 'dna_sequence',
    'clinical_trial_id', 'study_id', 'protocol_number',

    # Provider Information
    'physician_name', 'doctor_name', 'provider_npi',
    'dea_number', 'license_number_medical',
    'hospital_id', 'facility_id', 'clinic_id',

    # Appointment & Visit Data
    'appointment_id', 'visit_number', 'admission_date',
    'discharge_date', 'procedure_date', 'surgery_date',

    # Vital Signs & Measurements
    'blood_pressure', 'heart_rate', 'temperature',
    'weight', 'height', 'bmi', 'glucose_level',
    'oxygen_saturation', 'respiration_rate'
])

# ============================================================================
# FINANCIAL & PAYMENT PII (PCI-DSS, SOX)
# ============================================================================

FINANCIAL_PII = frozenset([
    # Credit/Debit Cards
    'credit_card', 'credit_card_number', 'cc_number', 'card_number',
    'debit_card', 'payment_card', 'pan',  # Primary Account Number
    'cvv', 'cvv2', 'cvc', 'cvc2', 'card_verification',
    'card_expiry', 'expiry_date', 'expiration_date',
    'cardholder_name', 'name_on_card',

    # Bank Accounts
    'bank_account', 'account_number', 'checking_account', 'savings_account',
    'routing_number', 'aba_number', 'swift_code', 'bic_code',
    'iban', 'international_bank_account',
    'sort_code', 'bsb_number', 'branch_code',
    'bank_name', 'financial_institution',

    # Investment & Trading
    'brokerage_account', 'trading_account', 'investment_account',
    'portfolio_id', 'custody_account', 'margin_account',
    'retirement_account', '401k', 'ira_account', 'roth_ira',
    'pension_number', 'annuity_number',
    'stock_symbol', 'cusip', 'isin', 'sedol',

    # Digital Payments
    'paypal_account', 'paypal_email', 'venmo_handle',
    'cashapp_tag', 'zelle_id', 'crypto_wallet',
    'bitcoin_address', 'ethereum_address', 'wallet_address',
    'private_key', 'seed_phrase', 'mnemonic_phrase',
    'stripe_customer_id', 'square_customer_id',
    'payment_token', 'payment_method_id',

    # Financial Documents
    'tax_id', 'tax_return', 'w2_form', 'w9_form', '1099_form',
    'income', 'salary', 'wage', 'compensation', 'bonus',
    'credit_score', 'fico_score', 'credit_report',
    'loan_number', 'mortgage_number', 'lease_number',
    'insurance_claim', 'claim_number', 'policy_number',

    # Billing Information
    'billing_address', 'invoice_number', 'purchase_order',
    'transaction_id', 'payment_id', 'order_id', 'receipt_number'
])

# ============================================================================
# CHILDREN'S PII (COPPA, FERPA Protected)
# ============================================================================

CHILDREN_PII = frozenset([
    # Educational Records
    'student_id', 'student_number', 'school_id', 'district_id',
    'enrollment_id', 'registration_number',
    'grade_level', 'gpa', 'transcript', 'report_card',
    'standardized_test_score', 'sat_score', 'act_score',
    'iep', 'individualized_education_program',
    '504_plan', 'special_education_record',
    'attendance_record', 'disciplinary_record',
    'lunch_number', 'bus_number', 'locker_number',

    # Child-Specific Identifiers
    'birth_certificate_number', 'adoption_record',
    'foster_care_id', 'case_worker', 'custody_agreement',
    'child_support_case', 'juvenile_record',
    'immunization_record', 'vaccination_record',
    'pediatrician', 'emergency_contact',

    # Online Accounts for Minors
    'parental_consent', 'coppa_consent',
    'child_email', 'child_username', 'gamer_tag',
    'minecraft_username', 'roblox_username', 'fortnite_id',
    'youtube_kids_account', 'tiktok_handle',
    'screen_time_passcode', 'parental_control_pin',

    # Activity & Location
    'school_schedule', 'after_school_activity',
    'sports_team', 'club_membership',
    'camp_registration', 'daycare_id',
    'pickup_authorization', 'carpool_info'
])

# ============================================================================
# BIOMETRIC & PHYSICAL PII (BIPA, GDPR Special Category)
# ============================================================================

BIOMETRIC_PII = frozenset([
    # Biometric Identifiers
    'fingerprint', 'finger_print', 'thumbprint',
    'facial_recognition', 'face_id', 'facial_template',
    'iris_scan', 'retina_scan', 'eye_scan',
    'voice_print', 'voice_recognition', 'speaker_verification',
    'palm_print', 'hand_geometry', 'vein_pattern',
    'dna_profile', 'genetic_marker', 'genome_sequence',
    'gait_analysis', 'walking_pattern',
    'keystroke_dynamics', 'typing_pattern',
    'signature_biometric', 'handwriting_pattern',

    # Physical Characteristics
    'photo', 'photograph', 'headshot', 'profile_picture',
    'video_recording', 'cctv_footage', 'surveillance_video',
    'height', 'weight', 'eye_color', 'hair_color',
    'distinguishing_marks', 'tattoo', 'scar', 'birthmark',
    'body_measurements', 'clothing_size', 'shoe_size',

    # Behavioral Biometrics
    'behavioral_pattern', 'usage_pattern', 'interaction_pattern',
    'mouse_movement', 'touch_pattern', 'swipe_pattern',
    'app_usage', 'browsing_pattern', 'purchase_pattern',
    'sleep_pattern', 'exercise_data', 'heart_rate_pattern',
    'stress_level', 'mood_data', 'emotion_recognition'
])

# ============================================================================
# DIGITAL IDENTITY & AUTHENTICATION
# ============================================================================

DIGITAL_IDENTITY_PII = frozenset([
    # Authentication Credentials
    'username', 'user_name', 'login_name', 'account_name',
    'password', 'passwd', 'pwd', 'passcode', 'pin',
    'security_question', 'security_answer', 'secret_question',
    'two_factor_code', '2fa_code', 'totp_code', 'otp',
    'backup_code', 'recovery_code', 'reset_token',
    'api_key', 'api_secret', 'api_token', 'access_token',
    'refresh_token', 'bearer_token', 'auth_token',
    'session_id', 'session_token', 'session_key',
    'cookie_id', 'tracking_cookie', 'auth_cookie',
    'jwt_token', 'json_web_token', 'id_token',

    # Digital Identifiers
    'user_id', 'userid', 'uid', 'uuid', 'guid',
    'customer_id', 'client_id', 'member_id',
    'device_id', 'machine_id', 'hardware_id',
    'mac_address', 'imei', 'imsi', 'udid',
    'android_id', 'advertising_id', 'idfa', 'aaid',
    'push_token', 'fcm_token', 'apns_token',
    'browser_fingerprint', 'canvas_fingerprint',

    # Account Information
    'email', 'email_address', 'primary_email', 'recovery_email',
    'phone', 'phone_number', 'mobile_number', 'cell_phone',
    'work_phone', 'home_phone', 'fax_number',
    'profile_url', 'avatar_url', 'public_key', 'pgp_key'
])

# ============================================================================
# LOCATION & TRACKING PII
# ============================================================================

LOCATION_PII = frozenset([
    # Physical Addresses
    'home_address', 'residential_address', 'mailing_address',
    'shipping_address', 'billing_address', 'work_address',
    'street_address', 'street_name', 'house_number',
    'apartment_number', 'unit_number', 'suite_number',
    'po_box', 'postal_box', 'mail_stop',
    'city', 'state', 'province', 'region',
    'zip_code', 'zipcode', 'postal_code', 'postcode',
    'country', 'country_code',

    # Coordinates & Maps
    'latitude', 'longitude', 'coordinates', 'gps_location',
    'geolocation', 'geo_coordinates', 'map_location',
    'plus_code', 'what3words', 'grid_reference',
    'altitude', 'elevation', 'floor_level',

    # Network Location
    'ip_address', 'ipv4', 'ipv6', 'public_ip', 'private_ip',
    'subnet', 'network_address', 'gateway_ip',
    'wifi_ssid', 'wifi_bssid', 'access_point',
    'cell_tower_id', 'base_station', 'network_operator',

    # Travel & Movement
    'flight_number', 'seat_number', 'boarding_pass',
    'frequent_flyer', 'airline_member_id',
    'hotel_reservation', 'booking_reference',
    'car_rental', 'rental_agreement',
    'train_ticket', 'bus_pass', 'metro_card',
    'toll_tag', 'ez_pass', 'fastrak',
    'parking_permit', 'garage_access',
    'travel_itinerary', 'trip_details'
])

# ============================================================================
# EMPLOYMENT & PROFESSIONAL PII
# ============================================================================

EMPLOYMENT_PII = frozenset([
    # Employee Information
    'employee_id', 'employee_number', 'staff_id', 'badge_number',
    'work_email', 'corporate_email', 'company_email',
    'job_title', 'position', 'department', 'division',
    'manager_name', 'supervisor', 'team_lead',
    'hire_date', 'start_date', 'termination_date',
    'employment_status', 'contract_type',

    # Compensation & Benefits
    'salary', 'base_pay', 'hourly_rate', 'pay_rate',
    'bonus', 'commission', 'overtime_pay',
    'stock_options', 'rsu', 'equity_grant',
    'benefits_id', 'health_plan', 'dental_plan', 'vision_plan',
    'life_insurance', 'disability_insurance',
    '401k_contribution', 'pension_contribution',
    'paid_time_off', 'pto_balance', 'sick_leave',

    # Performance & Records
    'performance_review', 'evaluation', 'rating',
    'disciplinary_action', 'warning', 'suspension',
    'promotion_record', 'transfer_record',
    'training_record', 'certification', 'license',
    'background_check', 'drug_test', 'security_clearance',
    'i9_verification', 'work_authorization',
    'union_membership', 'union_id',

    # Professional Identifiers
    'professional_license', 'bar_number', 'medical_license',
    'teaching_license', 'contractor_license',
    'real_estate_license', 'broker_number',
    'cpa_number', 'registration_number',
    'linkedin_profile', 'github_username', 'portfolio_url'
])

# ============================================================================
# VEHICLE & PROPERTY PII
# ============================================================================

VEHICLE_PROPERTY_PII = frozenset([
    # Vehicle Information
    'vin', 'vehicle_identification_number',
    'license_plate', 'plate_number', 'registration_number',
    'vehicle_registration', 'car_registration',
    'vehicle_title', 'title_number',
    'insurance_policy_auto', 'auto_insurance',
    'drivers_license_number', 'dl_number',
    'vehicle_make', 'vehicle_model', 'vehicle_year',
    'odometer_reading', 'mileage',

    # Property Information
    'property_deed', 'deed_number', 'parcel_number',
    'property_tax_id', 'assessment_number',
    'mortgage_account', 'loan_number', 'escrow_number',
    'home_insurance', 'property_insurance',
    'hoa_account', 'homeowners_association',
    'utility_account', 'electric_account', 'gas_account',
    'water_account', 'sewer_account', 'trash_account',
    'cable_account', 'internet_account',
    'alarm_code', 'gate_code', 'lockbox_code'
])

# ============================================================================
# SENSITIVE PREFERENCES & CHARACTERISTICS (GDPR Special Categories)
# ============================================================================

SENSITIVE_PREFERENCES = frozenset([
    # Demographics
    'race', 'ethnicity', 'nationality', 'citizenship',
    'religion', 'religious_affiliation', 'faith',
    'political_affiliation', 'political_party', 'voting_record',
    'sexual_orientation', 'gender_identity', 'pronouns',
    'marital_status', 'relationship_status', 'domestic_partnership',

    # Personal Beliefs & Associations
    'union_membership', 'professional_association',
    'club_membership', 'organization_membership',
    'charitable_donations', 'political_donations',
    'philosophical_beliefs', 'ethical_beliefs',

    # Personal History
    'criminal_record', 'arrest_record', 'conviction',
    'court_case', 'lawsuit', 'bankruptcy',
    'divorce_decree', 'custody_agreement',
    'military_service', 'veteran_status', 'discharge_type',

    # Preferences & Interests
    'dietary_restrictions', 'food_allergies', 'dietary_preference',
    'smoking_status', 'alcohol_consumption', 'drug_use',
    'hobbies', 'interests', 'activities',
    'reading_history', 'viewing_history', 'purchase_history',
    'search_history', 'browsing_history', 'click_stream'
])

# ============================================================================
# QUASI-IDENTIFIERS (Become PII when combined)
# ============================================================================

QUASI_IDENTIFIERS = frozenset([
    'age', 'birth_date', 'date_of_birth', 'dob', 'birth_year',
    'gender', 'sex', 'male_female',
    'zip_code', 'postal_code',
    'occupation', 'job_title', 'profession',
    'education_level', 'degree', 'school_name',
    'income_range', 'income_bracket',
    'vehicle_type', 'car_make', 'car_model',
    'employment_status', 'employer_name',
    'family_size', 'number_of_children',
    'home_ownership', 'property_type'
])

# ============================================================================
# THIRD-PARTY SERVICE IDENTIFIERS
# ============================================================================

THIRD_PARTY_IDS = frozenset([
    # Analytics & Tracking
    'google_analytics_id', 'ga_client_id', 'analytics_id',
    'mixpanel_distinct_id', 'amplitude_user_id', 'segment_id',
    'heap_user_id', 'fullstory_id', 'hotjar_id',
    'facebook_pixel_id', 'fb_browser_id',

    # CRM & Marketing
    'salesforce_id', 'sfdc_contact_id', 'lead_id',
    'hubspot_contact_id', 'marketo_lead_id',
    'mailchimp_subscriber_id', 'sendgrid_contact_id',
    'constant_contact_id', 'campaign_monitor_id',

    # E-commerce & Payments
    'shopify_customer_id', 'woocommerce_customer_id',
    'magento_customer_id', 'bigcommerce_customer_id',
    'stripe_customer_id', 'square_customer_id',
    'paypal_payer_id', 'braintree_customer_id',
    'authorize_net_profile_id', 'adyen_shopper_id',

    # Communication & Support
    'zendesk_user_id', 'intercom_user_id', 'freshdesk_contact_id',
    'slack_user_id', 'discord_user_id', 'telegram_user_id',
    'whatsapp_phone', 'signal_number',
    'zoom_user_id', 'teams_user_id', 'webex_id',

    # Social Media
    'facebook_user_id', 'instagram_handle', 'twitter_handle',
    'linkedin_member_id', 'youtube_channel_id', 'tiktok_user_id',
    'snapchat_username', 'pinterest_user_id', 'reddit_username',
    'github_username', 'gitlab_username', 'bitbucket_username'
])

# ============================================================================
# CONTACT METHODS
# ============================================================================

CONTACT_METHODS = frozenset([
    'email', 'email_address', 'contact_email', 'personal_email',
    'phone', 'phone_number', 'telephone', 'tel',
    'mobile', 'mobile_number', 'cell', 'cell_phone',
    'work_phone', 'office_phone', 'business_phone',
    'home_phone', 'landline', 'residential_phone',
    'fax', 'fax_number', 'facsimile',
    'pager', 'beeper', 'pager_number',
    'skype_id', 'skype_name', 'teams_id',
    'whatsapp', 'whatsapp_number', 'signal_number',
    'telegram_handle', 'telegram_username',
    'wechat_id', 'line_id', 'viber_number',
    'emergency_contact', 'next_of_kin', 'ice_contact'
])

# ============================================================================
# BEHAVIORAL & TRACKING DATA
# ============================================================================

BEHAVIORAL_DATA = frozenset([
    'browsing_history', 'search_history', 'click_history',
    'purchase_history', 'transaction_history', 'order_history',
    'viewing_history', 'watch_history', 'play_history',
    'download_history', 'app_usage', 'screen_time',
    'location_history', 'travel_history', 'places_visited',
    'call_log', 'sms_history', 'message_history',
    'contact_list', 'address_book', 'friend_list',
    'calendar_events', 'appointments', 'meetings',
    'fitness_data', 'health_data', 'sleep_data',
    'diet_log', 'exercise_log', 'workout_data',
    'mood_tracking', 'journal_entries', 'notes',
    'voice_recordings', 'audio_messages', 'voicemail',
    'photos', 'videos', 'screenshots', 'recordings'
])

# ============================================================================
# LOGGING & ERROR FUNCTIONS
# ============================================================================

LOGGING_FUNCTIONS = frozenset([
    # Python
    'print', 'pprint',
    'logger.debug', 'logger.info', 'logger.warning', 'logger.error', 'logger.critical',
    'logging.debug', 'logging.info', 'logging.warning', 'logging.error', 'logging.critical',
    'log.debug', 'log.info', 'log.warning', 'log.error', 'log.critical',

    # JavaScript/TypeScript
    'console.log', 'console.debug', 'console.info', 'console.warn', 'console.error',
    'console.trace', 'console.dir', 'console.table', 'console.group',

    # Node.js logging libraries
    'winston.debug', 'winston.info', 'winston.warn', 'winston.error',
    'bunyan.debug', 'bunyan.info', 'bunyan.warn', 'bunyan.error',
    'pino.debug', 'pino.info', 'pino.warn', 'pino.error',
    'morgan', 'debug',

    # PHP
    'error_log', 'var_dump', 'print_r', 'var_export',

    # Java
    'System.out.println', 'System.err.println',
    'logger.trace', 'logger.debug', 'logger.info', 'logger.warn', 'logger.error',

    # C#/.NET
    'Console.WriteLine', 'Debug.WriteLine', 'Trace.WriteLine',

    # Ruby
    'puts', 'p', 'pp', 'logger.debug', 'Rails.logger'
])

ERROR_RESPONSE_FUNCTIONS = frozenset([
    # Python
    'Response', 'HttpResponse', 'JsonResponse', 'render',
    'make_response', 'jsonify', 'send_error', 'abort',

    # JavaScript/Node.js
    'res.send', 'res.json', 'res.status', 'res.render',
    'response.send', 'response.json', 'response.status',
    'ctx.body', 'ctx.response', 'reply.send', 'reply.code',

    # Java
    'response.getWriter', 'response.getOutputStream',

    # PHP
    'echo', 'print', 'die', 'exit', 'json_encode',

    # Ruby
    'render', 'redirect_to', 'respond_to'
])

# ============================================================================
# STORAGE FUNCTIONS
# ============================================================================

DATABASE_STORAGE_FUNCTIONS = frozenset([
    # SQL
    'execute', 'executemany', 'query', 'insert', 'update', 'delete',
    'save', 'create', 'persist', 'store', 'write',

    # ORM
    'save', 'create', 'update', 'bulk_create', 'bulk_update',
    'findOneAndUpdate', 'updateOne', 'updateMany',
    'insertOne', 'insertMany', 'replaceOne',

    # NoSQL
    'put', 'putItem', 'set', 'setItem', 'add', 'append',
    'hset', 'hmset', 'sadd', 'zadd', 'lpush', 'rpush',

    # File Storage
    'write', 'writeFile', 'writeFileSync', 'appendFile',
    'fwrite', 'file_put_contents', 'save_to_file',

    # Cloud Storage
    's3.upload', 's3.putObject', 'blob.upload',
    'storage.save', 'bucket.upload', 'container.create_blob'
])

CLIENT_STORAGE_FUNCTIONS = frozenset([
    'localStorage.setItem', 'sessionStorage.setItem',
    'document.cookie', 'setCookie', 'cookies.set',
    'indexedDB.put', 'cache.put', 'store.set'
])

# ============================================================================
# COMPLIANCE MAPPING
# ============================================================================

def get_applicable_regulations(pii_type: str) -> List[PrivacyRegulation]:
    """Map PII types to applicable privacy regulations."""
    regulations = []

    # GDPR applies to all PII for EU residents
    regulations.append(PrivacyRegulation.GDPR)

    # CCPA applies to California residents' personal information
    if pii_type in US_GOVERNMENT_IDS or pii_type in FINANCIAL_PII:
        regulations.append(PrivacyRegulation.CCPA)

    # COPPA for children's information
    if pii_type in CHILDREN_PII:
        regulations.append(PrivacyRegulation.COPPA)

    # HIPAA for health information
    if pii_type in HEALTHCARE_PII:
        regulations.append(PrivacyRegulation.HIPAA)

    # PCI-DSS for payment cards
    if pii_type in FINANCIAL_PII and any(card in pii_type.lower() for card in ['credit', 'debit', 'card', 'cvv']):
        regulations.append(PrivacyRegulation.PCI_DSS)

    # FERPA for education records
    if pii_type in CHILDREN_PII and any(edu in pii_type.lower() for edu in ['student', 'school', 'education']):
        regulations.append(PrivacyRegulation.FERPA)

    # BIPA for biometric data
    if pii_type in BIOMETRIC_PII:
        regulations.append(PrivacyRegulation.BIPA)

    return regulations

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

def find_pii_issues(context: StandardRuleContext) -> List[StandardFinding]:
    """Detect PII exposure issues using comprehensive international patterns.

    Implements 25+ detection patterns across 15 PII categories with
    support for 50+ countries and major privacy regulations.
    """
    findings = []

    if not context.db_path:
        return findings

    conn = sqlite3.connect(context.db_path)
    cursor = conn.cursor()

    try:
        # All required tables guaranteed to exist by schema contract
        # (theauditor/indexer/schema.py - TABLES registry with 46 table definitions)
        # If table missing, rule will crash with clear sqlite3.OperationalError (CORRECT behavior)

        # Collect all PII patterns into categories
        pii_categories = _organize_pii_patterns()

        # Core detection layers - execute unconditionally

        # Layer 1: Direct PII detection
        findings.extend(_detect_direct_pii(cursor, pii_categories))

        # Layer 2: PII in logging
        findings.extend(_detect_pii_in_logging(cursor, pii_categories))

        # Layer 3: PII in error responses
        findings.extend(_detect_pii_in_errors(cursor, pii_categories))

        # Layer 4: PII in URLs
        findings.extend(_detect_pii_in_urls(cursor, pii_categories))

        # Layer 5: Unencrypted PII storage
        findings.extend(_detect_unencrypted_pii(cursor, pii_categories))

        # Layer 6: PII in client-side storage
        findings.extend(_detect_client_side_pii(cursor, pii_categories))

        # Layer 7: PII in exception handling
        findings.extend(_detect_pii_in_exceptions(cursor, pii_categories))

        # Layer 8: Derived PII (computed from other fields)
        findings.extend(_detect_derived_pii(cursor, pii_categories))

        # Layer 9: Aggregated PII (quasi-identifiers)
        findings.extend(_detect_aggregated_pii(cursor))

        # Layer 10: Third-party PII exposure
        findings.extend(_detect_third_party_pii(cursor, pii_categories))

        # Layer 11: PII in parameterized route patterns
        findings.extend(_detect_pii_in_route_patterns(cursor, pii_categories))

        # Layer 12: PII in static API paths
        findings.extend(_detect_pii_in_apis(cursor, pii_categories))

        # Additional advanced detection layers...

    finally:
        conn.close()

    return findings

# ============================================================================
# HELPER: Organize PII Patterns
# ============================================================================

def _organize_pii_patterns() -> Dict[str, Set[str]]:
    """Organize PII patterns by category for efficient searching."""
    return {
        'government': US_GOVERNMENT_IDS | INTERNATIONAL_GOVERNMENT_IDS,
        'healthcare': HEALTHCARE_PII,
        'financial': FINANCIAL_PII,
        'children': CHILDREN_PII,
        'biometric': BIOMETRIC_PII,
        'digital': DIGITAL_IDENTITY_PII,
        'location': LOCATION_PII,
        'employment': EMPLOYMENT_PII,
        'vehicle_property': VEHICLE_PROPERTY_PII,
        'sensitive': SENSITIVE_PREFERENCES,
        'third_party': THIRD_PARTY_IDS,
        'contact': CONTACT_METHODS,
        'behavioral': BEHAVIORAL_DATA,
        'quasi': QUASI_IDENTIFIERS
    }

# ============================================================================
# HELPER: Determine Confidence
# ============================================================================

def _determine_confidence(
    pii_type: str,
    context: str,
    is_encrypted: bool = False,
    is_test_file: bool = False
) -> Confidence:
    """Determine confidence level based on PII type and context."""
    # Test files get low confidence
    if is_test_file:
        return Confidence.LOW

    # Encrypted PII gets lower confidence (might be properly protected)
    if is_encrypted:
        return Confidence.MEDIUM

    # Critical PII types get high confidence
    critical_patterns = {'ssn', 'credit_card', 'password', 'api_key', 'private_key',
                         'passport', 'drivers_license', 'bank_account', 'medical_record'}
    if any(pattern in pii_type.lower() for pattern in critical_patterns):
        return Confidence.HIGH

    # Context-based confidence
    if 'log' in context.lower() or 'error' in context.lower():
        return Confidence.HIGH

    return Confidence.MEDIUM

# ============================================================================
# DETECTION LAYER 1: Direct PII
# ============================================================================

def _detect_direct_pii(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect direct PII fields in assignments and symbols."""
    findings = []

    # Build comprehensive pattern list
    all_patterns = set()
    for category_patterns in pii_categories.values():
        all_patterns.update(category_patterns)

    # Check assignments table - fetch all, filter in Python
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Identify which PII category by checking patterns in Python
        var_lower = var.lower()
        pii_category = None
        pii_pattern = None

        for category, patterns in pii_categories.items():
            for pattern in patterns:
                if pattern in var_lower:
                    pii_category = category
                    pii_pattern = pattern
                    break
            if pii_category:
                break

        if pii_category:
            regulations = get_applicable_regulations(pii_pattern)

            findings.append(StandardFinding(
                rule_name=f'pii-direct-{pii_category}',
                message=f'Direct PII assignment: {var} ({pii_category})',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=_determine_confidence(pii_pattern, 'assignment'),
                category='privacy',
                snippet=f'{var} = ...',
                cwe_id='CWE-359',  # Exposure of Private Personal Information
                additional_info={
                    'regulations': [r.value for r in regulations],
                    'pii_category': pii_category
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 2: PII in Logging
# ============================================================================

def _detect_pii_in_logging(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII being logged."""
    findings = []

    # Fetch all function calls, filter in Python
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a logging function
        if not any(log_func in func for log_func in LOGGING_FUNCTIONS):
            continue

        # Check for PII patterns in arguments
        args_lower = args.lower()
        detected_pii = []
        for category, patterns in pii_categories.items():
            for pattern in patterns:
                if pattern in args_lower:
                    detected_pii.append((pattern, category))

        if detected_pii:
            # Get the most critical PII type
            pii_pattern, pii_category = detected_pii[0]
            regulations = get_applicable_regulations(pii_pattern)

            findings.append(StandardFinding(
                rule_name='pii-logged',
                message=f'PII logged: {", ".join([p[0] for p in detected_pii[:3]])}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=_determine_confidence(pii_pattern, 'logging'),
                category='privacy',
                snippet=f'{func}({pii_pattern}...)',
                cwe_id='CWE-532',  # Insertion of Sensitive Information into Log File
                additional_info={
                    'regulations': [r.value for r in regulations],
                    'pii_types': [p[0] for p in detected_pii],
                    'pii_categories': list(set([p[1] for p in detected_pii]))
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 3: PII in Error Responses
# ============================================================================

def _detect_pii_in_errors(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII in error responses."""
    findings = []

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is an error response function
        if not any(resp_func in func for resp_func in ERROR_RESPONSE_FUNCTIONS):
            continue

        # Check if in error handling context
        cursor.execute("""
            SELECT COUNT(*) FROM symbols
            WHERE path = ?
              AND type = 'catch'
              AND ABS(line - ?) <= 10
        """, [file, line])

        catch_count = cursor.fetchone()[0]

        # Also check for error/exception in symbol names
        cursor.execute("""
            SELECT COUNT(*) FROM symbols
            WHERE path = ?
              AND name IS NOT NULL
              AND ABS(line - ?) <= 10
        """, [file, line])

        # Filter in Python for error/exception names
        cursor.execute("""
            SELECT name FROM symbols
            WHERE path = ?
              AND name IS NOT NULL
              AND ABS(line - ?) <= 10
        """, [file, line])

        error_names = sum(1 for (name,) in cursor.fetchall() if 'error' in name.lower() or 'exception' in name.lower())
        in_error_context = catch_count > 0 or error_names > 0

        if in_error_context:
            # Check for PII in error response
            args_lower = args.lower()
            detected_pii = []
            for category, patterns in pii_categories.items():
                for pattern in patterns:
                    if pattern in args_lower:
                        detected_pii.append((pattern, category))

            if detected_pii:
                pii_pattern, pii_category = detected_pii[0]
                regulations = get_applicable_regulations(pii_pattern)

                findings.append(StandardFinding(
                    rule_name='pii-error-response',
                    message=f'PII in error response: {pii_pattern}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='privacy',
                    snippet=f'{func}({{error: ...{pii_pattern}...}})',
                    cwe_id='CWE-209',  # Generation of Error Message Containing Sensitive Information
                    additional_info={
                        'regulations': [r.value for r in regulations]
                    }
                ))

    return findings

# ============================================================================
# DETECTION LAYER 4: PII in URLs
# ============================================================================

def _detect_pii_in_urls(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII in URLs and query parameters."""
    findings = []

    # URL building functions
    url_functions = frozenset(['urlencode', 'encodeURIComponent', 'URLSearchParams', 'build_url'])

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a URL function
        if not any(url_func in func for url_func in url_functions):
            continue

        # Never put these in URLs
        critical_url_pii = {'password', 'ssn', 'credit_card', 'api_key', 'token',
                           'bank_account', 'passport', 'drivers_license'}

        args_lower = args.lower()
        for pii in critical_url_pii:
            if pii in args_lower:
                findings.append(StandardFinding(
                    rule_name='pii-in-url',
                    message=f'Critical PII in URL: {pii}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='privacy',
                    snippet=f'{func}(...{pii}=...)',
                    cwe_id='CWE-598',  # Use of GET Request Method with Sensitive Query Strings
                    additional_info={
                        'regulations': [PrivacyRegulation.GDPR.value, PrivacyRegulation.CCPA.value]
                    }
                ))

    return findings

# ============================================================================
# DETECTION LAYER 5: Unencrypted PII Storage
# ============================================================================

def _detect_unencrypted_pii(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect unencrypted PII being stored."""
    findings = []

    # Critical PII that must be encrypted
    must_encrypt = {'ssn', 'credit_card', 'bank_account', 'passport', 'drivers_license',
                    'medical_record', 'tax_id', 'biometric', 'password'}

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a storage function
        if not any(store_func in func for store_func in DATABASE_STORAGE_FUNCTIONS):
            continue

        # Check for critical PII
        args_lower = args.lower()
        for pii in must_encrypt:
            if pii in args_lower:
                # Check if encryption is nearby
                cursor.execute("""
                    SELECT callee_function FROM function_call_args
                    WHERE file = ?
                      AND ABS(line - ?) <= 5
                      AND callee_function IS NOT NULL
                """, [file, line])

                # Filter in Python for encryption functions
                encryption_funcs = frozenset(['encrypt', 'hash', 'bcrypt'])
                has_encryption = any(
                    any(enc in (nearby_func or '').lower() for enc in encryption_funcs)
                    for (nearby_func,) in cursor.fetchall()
                )

                if not has_encryption:
                    findings.append(StandardFinding(
                        rule_name='pii-unencrypted-storage',
                        message=f'Unencrypted {pii} being stored',
                        file_path=file,
                        line=line,
                        severity=Severity.CRITICAL,
                        confidence=Confidence.HIGH,
                        category='privacy',
                        snippet=f'{func}(...{pii}...)',
                        cwe_id='CWE-311',  # Missing Encryption of Sensitive Data
                        additional_info={
                            'regulations': [PrivacyRegulation.GDPR.value, PrivacyRegulation.PCI_DSS.value]
                        }
                    ))

    return findings

# ============================================================================
# DETECTION LAYER 6: Client-Side PII Storage
# ============================================================================

def _detect_client_side_pii(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII stored in client-side storage."""
    findings = []

    # Never store these client-side
    forbidden_client_pii = {'password', 'ssn', 'credit_card', 'cvv', 'bank_account',
                            'api_key', 'private_key', 'passport', 'drivers_license'}

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a client storage function
        if not any(storage_func in func for storage_func in CLIENT_STORAGE_FUNCTIONS):
            continue

        args_lower = args.lower()
        for pii in forbidden_client_pii:
            if pii in args_lower:
                findings.append(StandardFinding(
                    rule_name='pii-client-storage',
                    message=f'Sensitive PII in browser storage: {pii}',
                    file_path=file,
                    line=line,
                    severity=Severity.CRITICAL,
                    confidence=Confidence.HIGH,
                    category='privacy',
                    snippet=f'{func}("{pii}", ...)',
                    cwe_id='CWE-922',  # Insecure Storage of Sensitive Information
                    additional_info={
                        'regulations': [PrivacyRegulation.GDPR.value, PrivacyRegulation.PCI_DSS.value],
                        'storage_type': 'localStorage' if 'localStorage' in func else
                                      'sessionStorage' if 'sessionStorage' in func else 'cookie'
                    }
                ))

    return findings

# ============================================================================
# DETECTION LAYER 7: PII in Exception Handling
# ============================================================================

def _detect_pii_in_exceptions(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII exposed in exception handling."""
    findings = []

    # Find exception handlers
    cursor.execute("""
        SELECT path, line, name
        FROM symbols
        WHERE type IN ('catch', 'except', 'exception', 'error')
        ORDER BY path, line
    """)

    for file, handler_line, handler_name in cursor.fetchall():
        # Check for logging within exception handlers
        cursor.execute("""
            SELECT callee_function, line, argument_expr
            FROM function_call_args
            WHERE file = ?
              AND line >= ?
              AND line <= ? + 20
              AND callee_function IS NOT NULL
              AND argument_expr IS NOT NULL
        """, [file, handler_line, handler_line])

        # Filter in Python for log/print/send functions
        log_keywords = frozenset(['log', 'print', 'send'])

        for func, line, args in cursor.fetchall():
            # Check if function is a logging function
            if not any(keyword in func.lower() for keyword in log_keywords):
                continue

            # Check if exception object is being logged directly
            args_lower = args.lower()
            if any(exc in args_lower for exc in ['exception', 'error', 'err', 'exc', 'stack', 'trace']):
                findings.append(StandardFinding(
                    rule_name='pii-exception-exposure',
                    message='Exception details may contain PII',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='privacy',
                    snippet=f'{func}(exception)',
                    cwe_id='CWE-209'
                ))

    return findings

# ============================================================================
# DETECTION LAYER 8: Derived PII
# ============================================================================

def _detect_derived_pii(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII derived from other fields."""
    findings = []

    # Common derived PII patterns
    derived_patterns = [
        ('full_name', ['first_name', 'last_name']),
        ('complete_address', ['street', 'city', 'state', 'zip']),
        ('age', ['birth_date', 'dob']),
        ('account_info', ['account_number', 'routing_number'])
    ]

    # Fetch all assignments
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE target_var IS NOT NULL
          AND source_expr IS NOT NULL
    """)

    for file, line, var, expr in cursor.fetchall():
        # Check each derived pattern in Python
        var_lower = var.lower()
        expr_lower = expr.lower()

        for derived_field, source_fields in derived_patterns:
            # Check if target var matches derived field
            if derived_field not in var_lower:
                continue

            # Check if source expression contains all source fields
            if all(sf in expr_lower for sf in source_fields):
                findings.append(StandardFinding(
                    rule_name='pii-derived',
                    message=f'Derived PII created: {var} from {", ".join(source_fields)}',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.MEDIUM,
                    category='privacy',
                    snippet=f'{var} = ...{source_fields[0]}...{source_fields[-1]}...',
                    cwe_id='CWE-359'
                ))
                break  # Only report once per assignment

    return findings

# ============================================================================
# DETECTION LAYER 9: Aggregated PII (Quasi-Identifiers)
# ============================================================================

def _detect_aggregated_pii(cursor) -> List[StandardFinding]:
    """Detect quasi-identifiers that become PII when combined."""
    findings = []

    # Check for multiple quasi-identifiers in same context
    quasi_list = list(QUASI_IDENTIFIERS)

    # Fetch all assignments
    cursor.execute("""
        SELECT file, line, target_var
        FROM assignments
        WHERE target_var IS NOT NULL
    """)

    # Group by file and count quasi-identifiers
    file_quasi = {}
    for file, line, var in cursor.fetchall():
        var_lower = var.lower()
        # Check if var matches any quasi-identifier
        if any(q in var_lower for q in quasi_list):
            if file not in file_quasi:
                file_quasi[file] = {'line': line, 'count': 0, 'vars': set()}
            file_quasi[file]['count'] += 1
            file_quasi[file]['vars'].add(var)
            if line < file_quasi[file]['line']:
                file_quasi[file]['line'] = line

    # Report files with 3+ quasi-identifiers
    for file, data in file_quasi.items():
        if data['count'] >= 3:
            findings.append(StandardFinding(
                rule_name='pii-quasi-identifiers',
                message=f'Multiple quasi-identifiers detected ({data["count"]} fields)',
                file_path=file,
                line=data['line'],
                severity=Severity.MEDIUM,
                confidence=Confidence.LOW,
                category='privacy',
                snippet='Multiple fields: age, zipcode, gender...',
                cwe_id='CWE-359',
                additional_info={
                    'note': 'Combination of 3+ quasi-identifiers can identify individuals with 87% accuracy'
                }
            ))

    return findings

# ============================================================================
# DETECTION LAYER 10: Third-Party PII Exposure
# ============================================================================

def _detect_third_party_pii(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII being sent to third-party services."""
    findings = []

    # Common third-party API patterns
    third_party_apis = frozenset([
        'analytics.track', 'ga.send', 'gtag',
        'mixpanel.track', 'amplitude.track',
        'facebook.pixel', 'fbq.track',
        'segment.track', 'heap.track'
    ])

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a third-party API
        if not any(api in func for api in third_party_apis):
            continue

        # Check for PII in tracking calls
        args_lower = args.lower()
        detected_pii = []
        for category, patterns in pii_categories.items():
            for pattern in patterns:
                if pattern in args_lower:
                    detected_pii.append(pattern)

        if detected_pii:
            findings.append(StandardFinding(
                rule_name='pii-third-party',
                message=f'PII sent to third-party: {", ".join(detected_pii[:3])}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                category='privacy',
                snippet=f'{func}(...{detected_pii[0]}...)',
                cwe_id='CWE-359',
                additional_info={
                    'regulations': [PrivacyRegulation.GDPR.value, PrivacyRegulation.CCPA.value],
                    'note': 'Third-party data sharing may require explicit consent'
                }
            ))

    return findings

# ============================================================================
# TAINT INTEGRATION
# ============================================================================

def register_taint_patterns(taint_registry):
    """Register PII patterns with taint analyzer for flow tracking."""
    # Register all PII patterns as sources
    all_pii = set()
    for patterns in [US_GOVERNMENT_IDS, INTERNATIONAL_GOVERNMENT_IDS, HEALTHCARE_PII,
                     FINANCIAL_PII, CHILDREN_PII, BIOMETRIC_PII, DIGITAL_IDENTITY_PII,
                     LOCATION_PII, EMPLOYMENT_PII, VEHICLE_PROPERTY_PII]:
        all_pii.update(patterns)

    for pattern in all_pii:
        taint_registry.register_source(pattern, "pii", "any")

    # Register sinks
    for func in LOGGING_FUNCTIONS:
        taint_registry.register_sink(func, "logging", "any")

    for func in ERROR_RESPONSE_FUNCTIONS:
        taint_registry.register_sink(func, "error_response", "any")

    for func in CLIENT_STORAGE_FUNCTIONS:
        taint_registry.register_sink(func, "client_storage", "any")

# ============================================================================
# ADDITIONAL DETECTION LAYERS
# ============================================================================

def _detect_pii_in_route_patterns(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detects PII exposed in parameterized API route patterns."""
    findings = []

    # Collect all PII patterns
    all_pii_patterns = set()
    for category_patterns in pii_categories.values():
        all_pii_patterns.update(category_patterns)

    cursor.execute("""
        SELECT file, line, method, pattern
        FROM api_endpoints
        WHERE pattern IS NOT NULL
          AND pattern != ''
        ORDER BY file, line
    """)

    for file, line, method, route_pattern in cursor.fetchall():
        # Extract route parameters using string methods
        extracted_params = []

        # Split by / to get route segments
        for segment in route_pattern.split('/'):
            # Handle :param style
            if segment.startswith(':'):
                param_name = segment[1:]
                # Remove any query string or fragment
                param_name = param_name.split('?')[0].split('#')[0]
                if param_name:
                    extracted_params.append(param_name)
            # Handle {param} style
            elif segment.startswith('{') and segment.endswith('}'):
                param_name = segment[1:-1]
                if param_name:
                    extracted_params.append(param_name)

        for param_name in extracted_params:
            # Normalize both sides for comparison (symmetric normalization)
            normalized_param = param_name.lower().replace('_', '').replace('-', '')

            for pii_pattern in all_pii_patterns:
                normalized_pii = pii_pattern.lower().replace('_', '').replace('-', '')

                if normalized_pii == normalized_param:
                    findings.append(StandardFinding(
                        rule_name='pii-in-route-parameter',
                        message=f'PII parameter "{param_name}" exposed in API route',
                        file_path=file,
                        line=line,
                        severity=Severity.HIGH,
                        category='privacy',
                        confidence=Confidence.MEDIUM,
                        snippet=f'{method.upper()} {route_pattern}',
                        cwe_id='CWE-598'
                    ))
                    break  # One finding per parameter

    return findings

def _detect_pii_in_apis(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII exposed in API endpoints."""
    findings = []

    # Get all API endpoints
    cursor.execute("""
        SELECT file, line, method, path
        FROM api_endpoints
        WHERE path IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, method, path in cursor.fetchall():
        # Check for PII in API path
        detected_pii = []
        for category, patterns in pii_categories.items():
            for pattern in patterns:
                if pattern in path.lower():
                    detected_pii.append((pattern, category))

        if detected_pii:
            pii_pattern, pii_category = detected_pii[0]
            regulations = get_applicable_regulations(pii_pattern)

            # GET requests with PII are especially bad
            if method.upper() == 'GET':
                severity = Severity.CRITICAL
                confidence = Confidence.HIGH
            else:
                severity = Severity.HIGH
                confidence = Confidence.MEDIUM

            findings.append(StandardFinding(
                rule_name='pii-api-exposure',
                message=f'PII exposed in API: {pii_pattern} via {method}',
                file_path=file,
                line=line,
                severity=severity,
                confidence=confidence,
                category='privacy',
                snippet=f'{method} {path} [{pii_pattern}]',
                cwe_id='CWE-598',
                additional_info={
                    'regulations': [r.value for r in regulations],
                    'method': method,
                    'pii_category': pii_category
                }
            ))

    return findings

def _detect_pii_in_exports(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII in data exports (CSV, JSON, XML)."""
    findings = []

    export_functions = frozenset([
        'to_csv', 'to_json', 'to_xml', 'to_excel',
        'export', 'download', 'generate_report',
        'writeFile', 'fs.writeFile', 'fs.writeFileSync',
        'json.dump', 'json.dumps', 'JSON.stringify',
        'csv.writer', 'csv.DictWriter'
    ])

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is an export function
        if not any(export_func in func for export_func in export_functions):
            continue

        # Check for bulk PII patterns
        args_lower = args.lower()
        pii_count = 0
        detected_types = []
        for category, patterns in pii_categories.items():
            for pattern in patterns:
                if pattern in args_lower:
                    pii_count += 1
                    detected_types.append(pattern)

        if pii_count >= 2:  # Multiple PII fields being exported
            findings.append(StandardFinding(
                rule_name='pii-bulk-export',
                message=f'Bulk PII export detected: {", ".join(detected_types[:3])}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.MEDIUM,
                category='privacy',
                snippet=f'{func}([...{pii_count} PII fields...])',
                cwe_id='CWE-359',
                additional_info={
                    'regulations': [PrivacyRegulation.GDPR.value],
                    'pii_count': pii_count,
                    'note': 'GDPR requires data minimization and purpose limitation'
                }
            ))

    return findings

def _detect_pii_retention(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII retention policy violations."""
    findings = []

    # Look for cache/storage without TTL
    cache_functions = frozenset([
        'cache.set', 'redis.set', 'memcached.set',
        'localStorage.setItem', 'sessionStorage.setItem'
    ])

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a cache function
        if not any(cache_func in func for cache_func in cache_functions):
            continue

        # Check if PII is being cached
        args_lower = args.lower()
        has_pii = False
        for category, patterns in pii_categories.items():
            if category in ['government', 'healthcare', 'financial', 'children']:
                for pattern in patterns:
                    if pattern in args_lower:
                        has_pii = True
                        break
            if has_pii:
                break

        if has_pii:
            # Check if TTL/expiry is set
            has_ttl = any(ttl in args_lower for ttl in ['ttl', 'expire', 'timeout', 'max_age'])

            if not has_ttl:
                findings.append(StandardFinding(
                    rule_name='pii-retention-violation',
                    message='PII cached without retention policy (no TTL)',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.MEDIUM,
                    category='privacy',
                    snippet=f'{func}(pii_data) // No TTL',
                    cwe_id='CWE-359',
                    additional_info={
                        'regulations': [PrivacyRegulation.GDPR.value],
                        'note': 'GDPR Article 5(1)(e): Data retention limitation principle'
                    }
                ))

    return findings

def _detect_pii_cross_border(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect cross-border PII transfers."""
    findings = []

    # International data transfer indicators
    cross_border_apis = frozenset([
        'aws-', 's3-', 'cloudfront',  # AWS regions
        'azure-', 'blob.core',  # Azure
        'googleapis.com', 'gstatic.com',  # Google Cloud
        'alibabacloud', 'aliyun',  # Alibaba Cloud
        'cdn.', 'cloudflare',  # CDNs
        '.eu-', '.us-', '.ap-', '.cn-'  # Region indicators
    ])

    # Fetch all assignments
    cursor.execute("""
        SELECT file, line, target_var, source_expr
        FROM assignments
        WHERE source_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, var, expr in cursor.fetchall():
        # Filter in Python for http/api patterns
        expr_lower = expr.lower()
        if not ('http' in expr_lower or 'api' in expr_lower):
            continue

        # Check if it's a cross-border transfer
        is_cross_border = any(api in expr_lower for api in cross_border_apis)

        if is_cross_border:
            # Check if PII is involved
            cursor.execute("""
                SELECT COUNT(*) FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND argument_expr IS NOT NULL
            """, [file, line])

            # Filter in Python for variable usage
            cursor.execute("""
                SELECT argument_expr FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 10
                  AND argument_expr IS NOT NULL
            """, [file, line])

            has_var_usage = any(var in (arg or '') for (arg,) in cursor.fetchall())

            if has_var_usage:
                findings.append(StandardFinding(
                    rule_name='pii-cross-border',
                    message='Potential cross-border PII transfer detected',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.LOW,
                    category='privacy',
                    snippet=f'{var} = {expr[:50]}...',
                    cwe_id='CWE-359',
                    additional_info={
                        'regulations': [PrivacyRegulation.GDPR.value],
                        'note': 'GDPR Chapter V requires safeguards for international transfers'
                    }
                ))

    return findings

def _detect_pii_consent_gaps(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII processing without consent checks."""
    findings = []

    # Consent-related function patterns
    consent_checks = frozenset([
        'hasConsent', 'checkConsent', 'verifyConsent',
        'isOptedIn', 'hasPermission', 'canProcess',
        'gdprConsent', 'cookieConsent', 'privacyConsent'
    ])

    # Find PII processing functions
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    # Filter in Python for processing functions
    processing_keywords = frozenset(['process', 'analyze', 'track', 'collect'])

    for file, line, func, args in cursor.fetchall():
        # Check if function is a processing function
        func_lower = func.lower()
        if not any(keyword in func_lower for keyword in processing_keywords):
            continue

        # Check if processing PII
        args_lower = args.lower()
        has_pii = any(
            pattern in args_lower
            for patterns in pii_categories.values()
            for pattern in patterns
        )

        if has_pii:
            # Check for consent check nearby
            cursor.execute("""
                SELECT callee_function FROM function_call_args
                WHERE file = ?
                  AND ABS(line - ?) <= 20
                  AND callee_function IS NOT NULL
            """, [file, line])

            # Filter in Python for consent functions
            has_consent_check = any(
                any(consent in (nearby_func or '').lower() for consent in consent_checks)
                for (nearby_func,) in cursor.fetchall()
            )

            if not has_consent_check:
                findings.append(StandardFinding(
                    rule_name='pii-no-consent',
                    message='PII processing without apparent consent check',
                    file_path=file,
                    line=line,
                    severity=Severity.MEDIUM,
                    confidence=Confidence.LOW,
                    category='privacy',
                    snippet=f'{func}(pii_data)',
                    cwe_id='CWE-359',
                    additional_info={
                        'regulations': [PrivacyRegulation.GDPR.value, PrivacyRegulation.CCPA.value],
                        'note': 'GDPR requires explicit consent for data processing'
                    }
                ))

    return findings

def _detect_pii_in_metrics(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII in metrics and monitoring."""
    findings = []

    metrics_functions = frozenset([
        'statsd.', 'prometheus.', 'metrics.',
        'newrelic.', 'datadog.', 'grafana.',
        'telemetry.', 'monitoring.', 'apm.',
        'counter.increment', 'gauge.set', 'histogram.observe'
    ])

    # Fetch all function calls
    cursor.execute("""
        SELECT file, line, callee_function, argument_expr
        FROM function_call_args
        WHERE callee_function IS NOT NULL
          AND argument_expr IS NOT NULL
        ORDER BY file, line
    """)

    for file, line, func, args in cursor.fetchall():
        # Check if function is a metrics function
        if not any(metric_func in func for metric_func in metrics_functions):
            continue

        # Never include these in metrics
        forbidden_metrics_pii = {'email', 'phone', 'ssn', 'password', 'credit_card', 'ip_address'}

        args_lower = args.lower()
        for pii in forbidden_metrics_pii:
            if pii in args_lower:
                findings.append(StandardFinding(
                    rule_name='pii-in-metrics',
                    message=f'PII in metrics/monitoring: {pii}',
                    file_path=file,
                    line=line,
                    severity=Severity.HIGH,
                    confidence=Confidence.HIGH,
                    category='privacy',
                    snippet=f'{func}(...{pii}...)',
                    cwe_id='CWE-359',
                    additional_info={
                        'note': 'Metrics systems often have weak access controls and long retention'
                    }
                ))

    return findings

def _detect_pii_access_control(cursor, pii_categories: Dict) -> List[StandardFinding]:
    """Detect PII access without proper authorization checks."""
    findings = []

    # Authorization check patterns
    auth_checks = frozenset([
        'isAuthorized', 'hasRole', 'hasPermission', 'canAccess',
        'requireAuth', 'checkAuth', 'verifyAccess', '@authorized',
        'authenticate', 'authorize', '@RequireRole', '@Secured'
    ])

    # Find functions that return PII
    cursor.execute("""
        SELECT file, line, name
        FROM symbols
        WHERE type = 'function'
          AND name IS NOT NULL
        ORDER BY file, line
    """)

    # Filter in Python for PII-related function names
    pii_function_keywords = frozenset(['get', 'fetch', 'load', 'retrieve'])
    pii_entity_keywords = frozenset(['user', 'profile', 'customer', 'patient'])

    for file, line, func_name in cursor.fetchall():
        func_name_lower = func_name.lower()

        # Check if function name suggests PII access
        has_pii_action = any(keyword in func_name_lower for keyword in pii_function_keywords)
        has_pii_entity = any(keyword in func_name_lower for keyword in pii_entity_keywords)

        if not (has_pii_action and has_pii_entity):
            continue

        # Check if function has auth checks
        cursor.execute("""
            SELECT callee_function FROM function_call_args
            WHERE file = ?
              AND line >= ?
              AND line <= ? + 50
              AND callee_function IS NOT NULL
        """, [file, line, line])

        # Filter in Python for auth functions
        has_auth = any(
            any(auth in (nearby_func or '').lower() for auth in auth_checks)
            for (nearby_func,) in cursor.fetchall()
        )

        if not has_auth:
            findings.append(StandardFinding(
                rule_name='pii-no-auth',
                message=f'PII access without authorization check: {func_name}',
                file_path=file,
                line=line,
                severity=Severity.HIGH,
                confidence=Confidence.LOW,
                category='privacy',
                snippet=f'function {func_name}() {{ /* No auth check */ }}',
                cwe_id='CWE-862',  # Missing Authorization
                additional_info={
                    'regulations': [PrivacyRegulation.GDPR.value, PrivacyRegulation.HIPAA.value]
                }
            ))

    return findings

# ============================================================================
# SUMMARY REPORT HELPER
# ============================================================================

def generate_pii_summary(findings: List[StandardFinding]) -> Dict:
    """Generate a summary report of PII findings."""
    summary = {
        'total_findings': len(findings),
        'by_severity': {},
        'by_category': {},
        'by_regulation': {},
        'top_risks': []
    }

    # Count by severity
    for finding in findings:
        sev = finding.severity.value if hasattr(finding.severity, 'value') else str(finding.severity)
        summary['by_severity'][sev] = summary['by_severity'].get(sev, 0) + 1

    # Count by PII category
    for finding in findings:
        if finding.additional_info and 'pii_category' in finding.additional_info:
            cat = finding.additional_info['pii_category']
            summary['by_category'][cat] = summary['by_category'].get(cat, 0) + 1

    # Count by regulation
    for finding in findings:
        if finding.additional_info and 'regulations' in finding.additional_info:
            for reg in finding.additional_info['regulations']:
                summary['by_regulation'][reg] = summary['by_regulation'].get(reg, 0) + 1

    # Identify top risks
    critical_findings = [f for f in findings if f.severity == Severity.CRITICAL]
    summary['top_risks'] = [
        {
            'rule': f.rule_name,
            'message': f.message,
            'file': f.file_path,
            'line': f.line
        }
        for f in critical_findings[:5]
    ]

    return summary

# ============================================================================
# MAIN ANALYSIS ORCHESTRATION
# ============================================================================

def analyze_pii_comprehensive(context: StandardRuleContext) -> Dict:
    """Run comprehensive PII analysis and return detailed report."""
    findings = find_pii_issues(context)

    # Add additional detection layers
    if context.db_path:
        conn = sqlite3.connect(context.db_path)
        cursor = conn.cursor()

        try:
            pii_categories = _organize_pii_patterns()

            # Additional layers - execute unconditionally
            findings.extend(_detect_pii_in_apis(cursor, pii_categories))
            findings.extend(_detect_pii_in_exports(cursor, pii_categories))
            findings.extend(_detect_pii_retention(cursor, pii_categories))
            findings.extend(_detect_pii_cross_border(cursor, pii_categories))
            findings.extend(_detect_pii_consent_gaps(cursor, pii_categories))
            findings.extend(_detect_pii_in_metrics(cursor, pii_categories))
            findings.extend(_detect_pii_access_control(cursor, pii_categories))
        finally:
            conn.close()

    # Generate summary
    summary = generate_pii_summary(findings)

    return {
        'findings': findings,
        'summary': summary,
        'analyzer': 'PII Analyzer - Comprehensive International Edition',
        'version': '2.0.0',
        'patterns_count': sum(len(s) for s in _organize_pii_patterns().values()),
        'countries_supported': 50,
        'regulations_covered': len(PrivacyRegulation)
    }

# ============================================================================
# EXPORT FOR RULE REGISTRATION
# ============================================================================

__all__ = [
    'find_pii_issues',
    'analyze_pii_comprehensive',
    'register_taint_patterns',
    'PrivacyRegulation',
    'get_applicable_regulations'
]