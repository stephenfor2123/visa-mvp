// ignore: unused_import
import 'package:intl/intl.dart' as intl;
import 'app_localizations.dart';

// ignore_for_file: type=lint

/// The translations for English (`en`).
class AppLocalizationsEn extends AppLocalizations {
  AppLocalizationsEn([String locale = 'en']) : super(locale);

  @override
  String get appName => 'Visa Helper';

  @override
  String get commonOk => 'OK';

  @override
  String get commonCancel => 'Cancel';

  @override
  String get commonLoading => 'Loading...';

  @override
  String get commonBack => 'Back';

  @override
  String get commonNext => 'Next';

  @override
  String get commonConfirm => 'Confirm';

  @override
  String get navHome => 'Home';

  @override
  String get navProfile => 'Profile';

  @override
  String get navMaterials => 'Materials';

  @override
  String get navLogin => 'Log In';

  @override
  String get navLogout => 'Log Out';

  @override
  String get navRegister => 'Sign Up';

  @override
  String get loginTitle => 'Welcome Back';

  @override
  String get loginSubtitle => 'Sign in with phone + password / SMS code';

  @override
  String get loginTabPwd => 'Password';

  @override
  String get loginTabSms => 'SMS Code';

  @override
  String get loginPhoneLabel => 'Phone';

  @override
  String get loginPhonePlaceholder => 'Enter your phone number';

  @override
  String get loginPwdLabel => 'Password';

  @override
  String get loginPwdPlaceholder => 'Enter your password';

  @override
  String get loginSmsLabel => 'Verification Code';

  @override
  String get loginSmsPlaceholder => '6-digit SMS code';

  @override
  String get loginSendCode => 'Send Code';

  @override
  String get loginResendCode => 'Resend';

  @override
  String get loginRemember => 'Stay signed in for 7 days';

  @override
  String get loginForgot => 'Forgot password?';

  @override
  String get loginSubmit => 'Log In';

  @override
  String get loginNoAccount => 'No account yet?';

  @override
  String get loginGoSignup => 'Sign up now';

  @override
  String get loginAgreementPrefix => 'I have read and agree to the';

  @override
  String get loginAgreementTerms => 'Terms of Service';

  @override
  String get loginAgreementAnd => 'and';

  @override
  String get loginAgreementPrivacy => 'Privacy Policy';

  @override
  String get homeSlogan => 'Visa Made Simple';

  @override
  String get homeSubtitle =>
      'Multi-country visa support · Smart material checklist · Denial insurance · Express service';

  @override
  String get homeCtaLogin => 'Log In';

  @override
  String get homeCtaExplore => 'Explore Countries';

  @override
  String get homeFeatureTitle => 'Why Choose Us';

  @override
  String get homeFeatureSubtitle =>
      'Turn the cumbersome visa process into 4 easy steps';

  @override
  String get homeFeature1Title => 'Auto Material Checklist';

  @override
  String get homeFeature1Desc =>
      'Auto-generate required materials by destination — no missing or wrong submissions.';

  @override
  String get homeFeature2Title => 'Denial Insurance';

  @override
  String get homeFeature2Desc =>
      '100% service fee refund if your visa is unfortunately denied.';

  @override
  String get homeFeature3Title => 'Template Library';

  @override
  String get homeFeature3Desc =>
      'Employment proof, bank statements, invitation letters — one-click templates.';

  @override
  String get homeFeature4Title => 'Affiliate Program';

  @override
  String get homeFeature4Desc =>
      'Refer a friend to apply — both of you get ¥50 coupon.';

  @override
  String get registerTitle => 'Create Your Account';

  @override
  String get registerSubtitle => 'Sign up with phone + SMS code + password';

  @override
  String get registerPhoneLabel => 'Phone Number';

  @override
  String get registerPhonePlaceholder => 'Enter your phone number';

  @override
  String get registerSmsLabel => 'SMS Code';

  @override
  String get registerSmsPlaceholder => '6-digit verification code';

  @override
  String get registerSendCode => 'Send Code';

  @override
  String get registerResendIn => 'Resend in';

  @override
  String get registerPwdLabel => 'Password';

  @override
  String get registerPwdPlaceholder => '8-32 chars, letters + digits';

  @override
  String get registerConfirmLabel => 'Confirm Password';

  @override
  String get registerConfirmPlaceholder => 'Re-enter your password';

  @override
  String get registerAgreementPrefix => 'I have read and agree to the';

  @override
  String get registerAgreementTerms => 'Terms of Service';

  @override
  String get registerAgreementAnd => 'and';

  @override
  String get registerAgreementPrivacy => 'Privacy Policy';

  @override
  String get registerSubmit => 'Sign Up';

  @override
  String get registerHaveAccount => 'Already have an account?';

  @override
  String get registerGoLogin => 'Log in';

  @override
  String get registerPwdHintShort => 'Password must be at least 8 characters';

  @override
  String get registerPwdHintLong => 'Password cannot exceed 32 characters';

  @override
  String get registerPwdHintFormat =>
      'Password must contain both letters and digits';

  @override
  String get registerPwdHintMismatch => 'Passwords do not match';

  @override
  String get registerPwdHintOk => 'Password strength: good';

  @override
  String get registerPwdStrengthWeak => 'Weak';

  @override
  String get registerPwdStrengthMedium => 'Medium';

  @override
  String get registerPwdStrengthStrong => 'Strong';

  @override
  String get materialsTitle => 'Material Collection';

  @override
  String get materialsSubtitle =>
      'Upload passport, photos and documents. We auto-recognize via OCR.';

  @override
  String get materialsTabPhoto => 'Photo';

  @override
  String get materialsTabPdf => 'Upload File';

  @override
  String get materialsTabVoice => 'Voice';

  @override
  String get materialsUploadTitle => 'Click or drag to upload';

  @override
  String get materialsUploadDesc => 'PDF, JPG, PNG, WebP — up to 10MB';

  @override
  String get materialsFormatHint => 'PDF / JPG / PNG / WebP';

  @override
  String get materialsSizeHint => 'Max 10MB';

  @override
  String get materialsUploading => 'Uploading';

  @override
  String get materialsUploadedOk => 'Upload complete';

  @override
  String get materialsCollectedCount => 'Collected';

  @override
  String get materialsEmptyTitle => 'No materials yet';

  @override
  String get materialsEmptyDesc => 'Click above to upload your first document';

  @override
  String get materialsEmptyCta => 'Upload Now';

  @override
  String get materialsItemType => 'Type';

  @override
  String get materialsTypePassport => 'Passport';

  @override
  String get materialsTypePhoto => 'Photo';

  @override
  String get materialsTypeProof => 'Proof';

  @override
  String get materialsTypeOther => 'Other';

  @override
  String get materialsOcrDone => 'OCR Done';

  @override
  String get materialsOcrProcessing => 'OCR Processing';

  @override
  String get materialsOcrFailed => 'OCR Failed';

  @override
  String get materialsOcrPending => 'Pending';

  @override
  String get materialsValidateBtn => 'Validate Materials';

  @override
  String get materialsValidating => 'Validating...';

  @override
  String get materialsContinueBtn => 'Continue to Order';

  @override
  String get errorsPhoneInvalid => 'Please enter a valid phone number';

  @override
  String get errorsPwdTooShort => 'Password must be at least 8 characters';

  @override
  String get errorsCodeInvalid => 'Please enter a 6-digit code';

  @override
  String get errorsNetwork => 'Network error, please retry';

  @override
  String get errorsAgreement => 'Please agree to the terms first';

  @override
  String get errorsFileTooBig => 'File too large (max 10MB)';

  @override
  String get errorsFileType => 'Unsupported file type';

  @override
  String get toastLoginSuccess => 'Logged in successfully';

  @override
  String get toastLoginFail => 'Login failed, please check your credentials';

  @override
  String get toastCodeSent => 'Code sent';

  @override
  String get toastCodeSendSuccess => 'Verification code sent';

  @override
  String get toastRegisterSuccess => 'Account created, please log in';

  @override
  String get toastRegisterFail => 'Registration failed, please try again';

  @override
  String get toastMaterialUploaded => 'Material uploaded';

  @override
  String get toastMaterialDeleted => 'Material deleted';

  @override
  String get toastMaterialsValidated => 'Materials validated';

  @override
  String get phoneCountryCn => 'China +86';

  @override
  String get phoneCountryId => 'Indonesia +62';

  @override
  String get phoneCountryVn => 'Vietnam +84';

  @override
  String get phoneCountryPh => 'Philippines +63';

  @override
  String get commonRetry => 'Retry';

  @override
  String get commonNetworkError => 'Network error, please retry';

  @override
  String get commonAppName => 'Visa Helper';

  @override
  String get destTitle => 'Choose Your Destination';

  @override
  String get destSubtitle => 'Select a country to start your visa application';

  @override
  String get destTourism => 'Tourism';

  @override
  String get destStudent => 'Student';

  @override
  String get destComingSoon => 'Coming Soon';

  @override
  String get destApplyNow => 'Apply Now';

  @override
  String get languageZh => '简体中文';

  @override
  String get languageEn => 'English';

  @override
  String get languageId => 'Bahasa Indonesia';

  @override
  String get languageVi => 'Tiếng Việt';

  @override
  String get profilePageTitle => 'My Profile';

  @override
  String get profilePageSubtitle => 'Manage your account';

  @override
  String get profileUserId => 'User ID';

  @override
  String get profileLanguagePref => 'Language';

  @override
  String get profileRegisterTime => 'Member Since';

  @override
  String get profileStatus => 'Status';

  @override
  String get profileStatusActive => 'Active';

  @override
  String get profileLoggedOut => 'Not logged in';

  @override
  String get profileGoLogin => 'Log in';

  @override
  String get profileForgotPwd => 'Reset Password';

  @override
  String get profileAgreement => 'Terms & Privacy';

  @override
  String get toastLogoutSuccess => 'Logged out successfully';

  @override
  String get orderPageTitle => 'My Orders';

  @override
  String get orderPageSubtitle => 'Track all your visa applications';

  @override
  String get orderTabAll => 'All';

  @override
  String get orderTabPendingPayment => 'Pending';

  @override
  String get orderTabPaid => 'Paid';

  @override
  String get orderTabReviewing => 'Reviewing';

  @override
  String get orderTabApproved => 'Approved';

  @override
  String get orderTabRejected => 'Rejected';

  @override
  String get orderLoading => 'Loading orders...';

  @override
  String get orderEmptyTitle => 'No orders yet';

  @override
  String get orderEmptyDesc => 'Your orders will appear here';

  @override
  String get orderEmptyAction => 'Go apply';

  @override
  String get orderItemAmount => 'Amount';

  @override
  String get orderItemVisaType => 'Visa Type';

  @override
  String get orderItemVisaTourism => 'Tourism';

  @override
  String get orderItemVisaStudent => 'Student';

  @override
  String get orderItemCreated => 'Created';

  @override
  String get orderItemPayNow => 'Pay Now';

  @override
  String get orderItemViewDetail => 'View Detail';

  @override
  String get orderRejectReasonLabel => 'Rejection Reason';

  @override
  String get orderLoadFailed => 'Failed to load orders';

  @override
  String get orderNotLoggedIn => 'Please log in first';

  @override
  String get orderGoLogin => 'Log In';

  @override
  String get paymentPageTitle => 'Payment';

  @override
  String get paymentPageSubtitle => 'Scan QR code to pay';

  @override
  String get paymentOrderLabel => 'Order';

  @override
  String get paymentAmountLabel => 'Amount';

  @override
  String get paymentQrHint => 'Open WeChat → Scan';

  @override
  String get paymentQrLoading => 'Generating QR code...';

  @override
  String get paymentQrExpired => 'QR Code Expired';

  @override
  String get paymentStatusPending => 'Pending';

  @override
  String get paymentStatusPaid => 'Paid';

  @override
  String get paymentStatusFailed => 'Failed';

  @override
  String get paymentPollingLabel => 'Polling';

  @override
  String get paymentPollingUnit => 'times';

  @override
  String get paymentPollNow => 'Polling now';

  @override
  String get paymentExpireLabel => 'Expires in';

  @override
  String get paymentExpireUnit => 'min';

  @override
  String get paymentBackBtn => 'Back';

  @override
  String get paymentBackSuccess => 'Payment successful!';

  @override
  String get paymentCreateFailed => 'Failed to create payment';

  @override
  String get paymentPollFailed => 'Failed to check payment status';

  @override
  String get forgotPageTitle => 'Reset Password';

  @override
  String get forgotPageSubtitle =>
      'Enter your account and set a new password to reset right away.';

  @override
  String get forgotPhoneLabel => 'Phone Number';

  @override
  String get forgotPhonePlaceholder => 'Enter your phone number';

  @override
  String get forgotSmsLabel => 'SMS Code';

  @override
  String get forgotSmsPlaceholder => '6-digit code';

  @override
  String get forgotSendCode => 'Send Code';

  @override
  String get forgotResendCode => 'Resend';

  @override
  String get forgotNewPwdLabel => 'New Password';

  @override
  String get forgotNewPwdPlaceholder => '8+ characters';

  @override
  String get forgotConfirmPwdLabel => 'Confirm Password';

  @override
  String get forgotConfirmPwdPlaceholder => 'Re-enter new password';

  @override
  String get forgotSubmit => 'Reset Password';

  @override
  String get forgotSubmitting => 'Resetting...';

  @override
  String get forgotBackLogin => 'Back to Log In';

  @override
  String get forgotSuccessTitle => 'Password Reset!';

  @override
  String get forgotSuccessDesc => 'Your password has been updated successfully';

  @override
  String get forgotGoLogin => 'Log In Now';

  @override
  String get errorsPwdMismatch => 'Passwords do not match';

  @override
  String get agreementPageTitle => 'Legal';

  @override
  String get agreementPageSubtitle => 'Terms of Service & Privacy Policy';

  @override
  String get agreementTabTerms => 'Terms of Service';

  @override
  String get agreementTabPrivacy => 'Privacy Policy';

  @override
  String get agreementTermsTitle => 'Terms of Service';

  @override
  String get agreementTermsEffective => 'Effective: January 1, 2026';

  @override
  String get agreementTermsSection1Title => '1. Service Scope';

  @override
  String get agreementTermsSection1Body =>
      'Visa Helper provides visa application advisory and document preparation services. We act as an intermediary between users and embassies/consulates and do not guarantee visa approval. Visa decisions are made solely by the respective authorities.';

  @override
  String get agreementTermsSection2Title => '2. User Responsibilities';

  @override
  String get agreementTermsSection2Body =>
      'Users must ensure all submitted materials are authentic and complete. Providing false information may result in application rejection, fees forfeited, or legal liability.';

  @override
  String get agreementTermsSection3Title => '3. Service Fees';

  @override
  String get agreementTermsSection3Body =>
      'Service fees are charged for document preparation and advisory services, not for visa approval. Fees are non-refundable unless otherwise specified in the denial insurance policy.';

  @override
  String get agreementTermsSection4Title => '4. Disclaimer';

  @override
  String get agreementTermsSection4Body =>
      'Visa Helper is not liable for visa denial, processing delays, or any consequences arising from user-provided false information or incomplete materials.';

  @override
  String get agreementPrivacyTitle => 'Privacy Policy';

  @override
  String get agreementPrivacyEffective => 'Effective: January 1, 2026';

  @override
  String get agreementPrivacySection1Title => '1. Data We Collect';

  @override
  String get agreementPrivacySection1Body =>
      'We collect personal information (name, passport, phone) and materials (passport scan, photos) solely for visa application purposes. Data is encrypted in transit and stored securely.';

  @override
  String get agreementPrivacySection2Title => '2. Data Usage';

  @override
  String get agreementPrivacySection2Body =>
      'Your data is used exclusively for: generating application materials, communicating with you about your application status, and improving our services. We do not sell or share your data with third parties for marketing.';

  @override
  String get agreementPrivacySection3Title => '3. Data Retention';

  @override
  String get agreementPrivacySection3Body =>
      'Application data is retained for 24 months after service completion, then deleted. You may request deletion at any time by contacting support@visahelper.com.';

  @override
  String get agreementPrivacySection4Title => '4. Security';

  @override
  String get agreementPrivacySection4Body =>
      'We use AES-256 encryption for stored data and TLS 1.3 for data in transit. Access is restricted to authorized personnel and audited quarterly.';

  @override
  String get orderdetailPageTitle => 'Order Detail';

  @override
  String get orderdetailPageSubtitle => 'Track your visa application';

  @override
  String get orderdetailOrderNoLabel => 'Order No.';

  @override
  String get orderdetailUpdatedAtLabel => 'Updated at';

  @override
  String get orderdetailSectionTimeline => 'Application Timeline';

  @override
  String get orderdetailSectionPassport => 'Passport Info';

  @override
  String get orderdetailFieldName => 'Passport Name';

  @override
  String get orderdetailFieldPassportNo => 'Passport No.';

  @override
  String get orderdetailStepCreated => 'Order Created';

  @override
  String get orderdetailStepSubmitted => 'Submitted';

  @override
  String get orderdetailStepReviewing => 'Under Review';

  @override
  String get orderdetailStepApproved => 'Approved';

  @override
  String get orderdetailStepRejected => 'Rejected';

  @override
  String get orderdetailRetryBtn => 'Retry';

  @override
  String get orderdetailLogoutBtn => 'Log Out';

  @override
  String get orderdetailWsConnected => 'Live';

  @override
  String get orderdetailWsConnecting => 'Connecting';

  @override
  String get orderdetailPollingLabel => 'Polling';

  @override
  String get orderdetailPollingUnit => 's';

  @override
  String get ordernewPageTitle => 'Visa Application';

  @override
  String get ordernewPageSubtitle => 'Complete your application form';

  @override
  String get ordernewDestLabel => 'Destination';

  @override
  String get ordernewOcrPrefilled => 'OCR prefilled';

  @override
  String get ordernewBtnBack => 'Back';

  @override
  String get ordernewTabBasic => 'Basic';

  @override
  String get ordernewTabTravel => 'Travel';

  @override
  String get ordernewTabEmergency => 'Emergency';

  @override
  String get ordernewSectionBasic => 'Basic Information';

  @override
  String get ordernewSectionTravel => 'Travel Details';

  @override
  String get ordernewSectionEmergency => 'Emergency Contact';

  @override
  String get ordernewFieldSurname => 'Surname';

  @override
  String get ordernewFieldGiven => 'Given Name';

  @override
  String get ordernewFieldDob => 'Date of Birth';

  @override
  String get ordernewFieldNationality => 'Nationality';

  @override
  String get ordernewFieldPassportNo => 'Passport Number';

  @override
  String get ordernewFieldPassportExp => 'Passport Expiry';

  @override
  String get ordernewFieldArrival => 'Arrival Date';

  @override
  String get ordernewFieldDeparture => 'Departure Date';

  @override
  String get ordernewFieldPurpose => 'Purpose of Visit';

  @override
  String get ordernewFieldEmergencyName => 'Contact Name';

  @override
  String get ordernewFieldEmergencyPhone => 'Contact Phone';

  @override
  String get ordernewFieldEmergencyRel => 'Relationship';

  @override
  String get ordernewSubmit => 'Submit Application';

  @override
  String get ordernewSubmitting => 'Submitting...';

  @override
  String get applyTitle => 'Apply for a Visa';

  @override
  String get applySub => '4 steps to your visa';

  @override
  String get applyStepCountry => 'Choose Destination';

  @override
  String get applyStepChecklist => 'Materials Checklist';

  @override
  String get applyStepTrip => 'Trip Info';

  @override
  String get applyStepConfirm => 'Confirm';

  @override
  String get applyFeeLabel => 'Fee';

  @override
  String get applyProcessingLabel => 'Processing';

  @override
  String get applyValidityLabel => 'Validity';

  @override
  String get applyVisaType => 'Visa Type';

  @override
  String get applyVisaTourism => 'Tourism';

  @override
  String get applyVisaBusiness => 'Business';

  @override
  String get applyVisaStudent => 'Student';

  @override
  String get applyVisaFamily => 'Family';

  @override
  String get applyVisaOther => 'Other';

  @override
  String get applyDepartDate => 'Departure Date';

  @override
  String get applyReturnDate => 'Return Date';

  @override
  String get applyDepartCity => 'Departure City';

  @override
  String get applyDepartCityPh => 'e.g. Shanghai';

  @override
  String get applyEmergencyContact => 'Emergency Contact';

  @override
  String get applyEmergencyPh => 'e.g. John +86 138xxxx';

  @override
  String get applyPurpose => 'Trip Purpose';

  @override
  String get applyPurposePh => 'Briefly describe purpose';

  @override
  String get applyBack => '← Back';

  @override
  String get applyNextMaterials => 'Next: Fill Form';

  @override
  String get applyNextConfirm => 'Next: Confirm';

  @override
  String get applyPickDate => 'Pick a date';

  @override
  String get applyConfirmSubmit => 'Confirm & Submit';

  @override
  String get applySubmitting => 'Submitting…';

  @override
  String get applyRequired => 'req';

  @override
  String get diagnoseTitle => 'Pre-Assessment';

  @override
  String get diagnoseSub => 'Check your approval odds first';

  @override
  String get diagnoseStepForm => 'Tell us about yourself';

  @override
  String get diagnoseResult => 'Your Result';

  @override
  String get diagnoseFactors => 'Factors';

  @override
  String get diagnoseSuggestions => 'Suggestions';

  @override
  String get diagnoseCtaApply => 'Apply for this country →';

  @override
  String get diagnoseRestart => 'Re-assess';

  @override
  String get diagnoseLevelHigh => 'High chance';

  @override
  String get diagnoseLevelMedium => 'Medium';

  @override
  String get diagnoseLevelLow => 'Low chance';

  @override
  String get diagnoseMarital => 'Marital Status';

  @override
  String get diagnoseMaritalSingle => 'Single';

  @override
  String get diagnoseMaritalMarried => 'Married';

  @override
  String get diagnoseMaritalDivorced => 'Divorced';

  @override
  String get diagnoseMaritalWidowed => 'Widowed';

  @override
  String get diagnoseIncome => 'Monthly Income (CNY)';

  @override
  String get diagnoseIncomeBelow5k => '<5k';

  @override
  String get diagnoseIncome5k15k => '5k-15k';

  @override
  String get diagnoseIncome15k30k => '15k-30k';

  @override
  String get diagnoseIncome30k100k => '30k-100k';

  @override
  String get diagnoseIncomeAbove100k => '>100k';

  @override
  String get diagnosePurpose => 'Travel Purpose';

  @override
  String get diagnosePurposeBusiness => 'Business';

  @override
  String get diagnosePurposeTourism => 'Tourism';

  @override
  String get diagnosePurposeFamily => 'Family';

  @override
  String get diagnosePurposeStudy => 'Study';

  @override
  String get diagnosePurposeOther => 'Other';

  @override
  String get diagnoseTravelHistory => 'Travel History (5y)';

  @override
  String get diagnoseTravelNone => 'None';

  @override
  String get diagnoseTravel1to3 => '1-3';

  @override
  String get diagnoseTravel4to10 => '4-10';

  @override
  String get diagnoseTravelAbove10 => '10+';

  @override
  String get diagnoseVisaHistory => 'Visa History';

  @override
  String get diagnoseVisaNone => 'None';

  @override
  String get diagnoseVisa1to2 => '1-2';

  @override
  String get diagnoseVisaAbove2 => '2+';

  @override
  String get diagnoseEmployment => 'Employment';

  @override
  String get diagnoseEmpEmployed => 'Employed';

  @override
  String get diagnoseEmpFreelancer => 'Freelancer';

  @override
  String get diagnoseEmpStudent => 'Student';

  @override
  String get diagnoseEmpRetired => 'Retired';

  @override
  String get diagnoseEmpUnemployed => 'Unemployed';

  @override
  String get diagnoseAge => 'Age (optional)';

  @override
  String get diagnoseAgePh => 'e.g. 30';

  @override
  String get diagnoseSoloFemale => 'Solo female traveler';

  @override
  String get diagnoseSubmit => 'View Result';

  @override
  String get diagnoseSubmitting => 'Assessing…';

  @override
  String get diagnoseReselect => '← Re-select country';

  @override
  String get diagnoseStart => 'Start Assessment';

  @override
  String get resourcesTitle => 'Visa Q&A';

  @override
  String get resourcesSub => 'AI answers from official sources';

  @override
  String get resourcesHint => 'e.g. US visa fee';

  @override
  String get resourcesEmpty => 'Start asking';

  @override
  String get resourcesFollowup => 'Follow up';

  @override
  String get resourcesSources => 'Sources';

  @override
  String get resourcesRelevance => 'Relevance';

  @override
  String get contactTitle => 'Contact Us';

  @override
  String get contactSub => 'Replies within business hours (UTC+8, 9-18h)';

  @override
  String get contactEmail => 'Email';

  @override
  String get contactEmailAddr => 'support@htex.app';

  @override
  String get contactEmailSub => 'Reply within 24 hours';

  @override
  String get contactChat => 'Live Chat';

  @override
  String get contactChatSub => 'Real-time on weekdays';

  @override
  String get contactBug => 'Bug Report';

  @override
  String get contactBugSub => 'Engineers see directly';

  @override
  String get contactBiz => 'Business';

  @override
  String get contactBizAddr => 'biz@htex.app';

  @override
  String get contactBizSub => 'Affiliate / Travel agencies';

  @override
  String get contactTip =>
      'Emergencies: contact your local embassy. Htex cannot replace official channels.';

  @override
  String get passportUploadTitle => 'Upload Passport';

  @override
  String get passportUploadSub => 'Snap a clear passport photo';

  @override
  String get passportUploadTip =>
      'Make sure the bio page is aligned and well-lit';

  @override
  String get passportGallery => 'Gallery';

  @override
  String get passportCamera => 'Camera';

  @override
  String get passportRecognize => 'Recognize';

  @override
  String get passportRecognizing => 'Recognizing…';

  @override
  String get passportReviewTitle => 'Confirm Passport Info';

  @override
  String get passportReviewDetected => '✓ Detected as passport';

  @override
  String get passportReviewWarn => '⚠️ Not a passport';

  @override
  String get passportReviewConfirm => 'Confirm & Continue';

  @override
  String get passportReviewRetake => 'Retake';

  @override
  String get passportReviewPassportNo => 'Passport No.';

  @override
  String get passportReviewSurname => 'Surname';

  @override
  String get passportReviewGivenName => 'Given Name';

  @override
  String get passportReviewSex => 'Sex (M / F)';

  @override
  String get passportReviewNationality => 'Nationality';

  @override
  String get passportReviewDob => 'Date of Birth (YYYY-MM-DD)';

  @override
  String get passportReviewExpiry => 'Expiry (YYYY-MM-DD)';

  @override
  String get loginAccountTab => 'Account';

  @override
  String get loginSmsTab => 'SMS';

  @override
  String get loginAccountLabel => 'Email or Username';

  @override
  String get loginAccountPh => 'user@example.com or username';

  @override
  String get registerUsernameLabel => 'Username';

  @override
  String get registerUsernamePh => '3-32 chars, starts with letter/digit';

  @override
  String get registerUsernameHint =>
      '3-32 chars [A-Za-z0-9_.-], letter/digit start';

  @override
  String get registerEmailLabel => 'Email';

  @override
  String get registerEmailPh => 'user@example.com';

  @override
  String get registerNicknameLabel => 'Nickname (optional)';

  @override
  String get registerNicknamePh => 'What should we call you?';

  @override
  String get registerEmailInvalid => 'Invalid email format';

  @override
  String get registerUsernameInvalid => 'Invalid username format';

  @override
  String get homeSloganZh => 'Infinite possibilities, by your side';

  @override
  String get homeCtaDiagnose => 'Check Odds';

  @override
  String get homeCtaAsk => 'Ask Policy';

  @override
  String get homeTrust => '100k+ users · 99% approval';

  @override
  String get homeFeatureUploadTitle => 'Upload Passport';

  @override
  String get homeFeatureUploadSub => 'Auto OCR';

  @override
  String get homeFeatureDiagnoseTitle => 'Pre-Assessment';

  @override
  String get homeFeatureDiagnoseSub => 'Risk score';

  @override
  String get homeFeatureResourcesTitle => 'Policy Q&A';

  @override
  String get homeFeatureResourcesSub => 'RAG from 4 sources';

  @override
  String get homeFeatureContactTitle => 'Contact Us';

  @override
  String get homeFeatureContactSub => 'Weekdays 9-18h';

  @override
  String get homeHotVisa => 'Popular Destinations';

  @override
  String get homeViewAll => 'View all →';

  @override
  String get homeSectionFeatures => 'What you can do with Htex';

  @override
  String get homeFooterUpload => 'Upload';

  @override
  String get homeFooterDiagnose => 'Assess';

  @override
  String get homeFooterQa => 'Q&A';

  @override
  String get homeFooterContact => 'Support';

  @override
  String get homeHeroCityPrefix => 'Endless possibilities, by your side';

  @override
  String get homeFromPrice => 'FROM';

  @override
  String get homeApplyNow => 'Apply Now';

  @override
  String get homeFooterCopyright => 'Htex · Wherever you go, life is infinite';

  @override
  String get destinationsTitle => 'Choose Destination';

  @override
  String get destinationsHero => 'Popular Visas';

  @override
  String get destinationsSchengen => 'Schengen 26';

  @override
  String get destinationsExpand => 'Expand';

  @override
  String get destinationsCollapse => 'Collapse';

  @override
  String get destinationsValid => 'VALID';

  @override
  String get destinationsApply => 'Apply';

  @override
  String get destinationsSearch => 'Search country';

  @override
  String get selfieStart => 'Take Selfie';

  @override
  String get selfieRetake => 'Retake';

  @override
  String get selfieHint => 'Tap below to start';
}
