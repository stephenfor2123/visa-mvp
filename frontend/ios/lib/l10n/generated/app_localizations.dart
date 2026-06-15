import 'dart:async';

import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_localizations/flutter_localizations.dart';
import 'package:intl/intl.dart' as intl;

import 'app_localizations_en.dart';
import 'app_localizations_id.dart';
import 'app_localizations_vi.dart';
import 'app_localizations_zh.dart';

// ignore_for_file: type=lint

/// Callers can lookup localized strings with an instance of AppLocalizations
/// returned by `AppLocalizations.of(context)`.
///
/// Applications need to include `AppLocalizations.delegate()` in their app's
/// `localizationDelegates` list, and the locales they support in the app's
/// `supportedLocales` list. For example:
///
/// ```dart
/// import 'generated/app_localizations.dart';
///
/// return MaterialApp(
///   localizationsDelegates: AppLocalizations.localizationsDelegates,
///   supportedLocales: AppLocalizations.supportedLocales,
///   home: MyApplicationHome(),
/// );
/// ```
///
/// ## Update pubspec.yaml
///
/// Please make sure to update your pubspec.yaml to include the following
/// packages:
///
/// ```yaml
/// dependencies:
///   # Internationalization support.
///   flutter_localizations:
///     sdk: flutter
///   intl: any # Use the pinned version from flutter_localizations
///
///   # Rest of dependencies
/// ```
///
/// ## iOS Applications
///
/// iOS applications define key application metadata, including supported
/// locales, in an Info.plist file that is built into the application bundle.
/// To configure the locales supported by your app, you’ll need to edit this
/// file.
///
/// First, open your project’s ios/Runner.xcworkspace Xcode workspace file.
/// Then, in the Project Navigator, open the Info.plist file under the Runner
/// project’s Runner folder.
///
/// Next, select the Information Property List item, select Add Item from the
/// Editor menu, then select Localizations from the pop-up menu.
///
/// Select and expand the newly-created Localizations item then, for each
/// locale your application supports, add a new item and select the locale
/// you wish to add from the pop-up menu in the Value field. This list should
/// be consistent with the languages listed in the AppLocalizations.supportedLocales
/// property.
abstract class AppLocalizations {
  AppLocalizations(String locale)
      : localeName = intl.Intl.canonicalizedLocale(locale.toString());

  final String localeName;

  static AppLocalizations of(BuildContext context) {
    return Localizations.of<AppLocalizations>(context, AppLocalizations)!;
  }

  static const LocalizationsDelegate<AppLocalizations> delegate =
      _AppLocalizationsDelegate();

  /// A list of this localizations delegate along with the default localizations
  /// delegates.
  ///
  /// Returns a list of localizations delegates containing this delegate along with
  /// GlobalMaterialLocalizations.delegate, GlobalCupertinoLocalizations.delegate,
  /// and GlobalWidgetsLocalizations.delegate.
  ///
  /// Additional delegates can be added by appending to this list in
  /// MaterialApp. This list does not have to be used at all if a custom list
  /// of delegates is preferred or required.
  static const List<LocalizationsDelegate<dynamic>> localizationsDelegates =
      <LocalizationsDelegate<dynamic>>[
    delegate,
    GlobalMaterialLocalizations.delegate,
    GlobalCupertinoLocalizations.delegate,
    GlobalWidgetsLocalizations.delegate,
  ];

  /// A list of this localizations delegate's supported locales.
  static const List<Locale> supportedLocales = <Locale>[
    Locale('en'),
    Locale('id'),
    Locale('vi'),
    Locale('zh')
  ];

  /// App brand name shown in header and login footer.
  ///
  /// In en, this message translates to:
  /// **'Visa Helper'**
  String get appName;

  /// No description provided for @commonOk.
  ///
  /// In en, this message translates to:
  /// **'OK'**
  String get commonOk;

  /// No description provided for @commonCancel.
  ///
  /// In en, this message translates to:
  /// **'Cancel'**
  String get commonCancel;

  /// No description provided for @commonLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading...'**
  String get commonLoading;

  /// No description provided for @commonBack.
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get commonBack;

  /// No description provided for @commonNext.
  ///
  /// In en, this message translates to:
  /// **'Next'**
  String get commonNext;

  /// No description provided for @commonConfirm.
  ///
  /// In en, this message translates to:
  /// **'Confirm'**
  String get commonConfirm;

  /// No description provided for @navHome.
  ///
  /// In en, this message translates to:
  /// **'Home'**
  String get navHome;

  /// No description provided for @navProfile.
  ///
  /// In en, this message translates to:
  /// **'Profile'**
  String get navProfile;

  /// No description provided for @navMaterials.
  ///
  /// In en, this message translates to:
  /// **'Materials'**
  String get navMaterials;

  /// No description provided for @navLogin.
  ///
  /// In en, this message translates to:
  /// **'Log In'**
  String get navLogin;

  /// No description provided for @navLogout.
  ///
  /// In en, this message translates to:
  /// **'Log Out'**
  String get navLogout;

  /// No description provided for @navRegister.
  ///
  /// In en, this message translates to:
  /// **'Sign Up'**
  String get navRegister;

  /// No description provided for @loginTitle.
  ///
  /// In en, this message translates to:
  /// **'Welcome Back'**
  String get loginTitle;

  /// No description provided for @loginSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign in with phone + password / SMS code'**
  String get loginSubtitle;

  /// No description provided for @loginTabPwd.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get loginTabPwd;

  /// No description provided for @loginTabSms.
  ///
  /// In en, this message translates to:
  /// **'SMS Code'**
  String get loginTabSms;

  /// No description provided for @loginPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Phone'**
  String get loginPhoneLabel;

  /// No description provided for @loginPhonePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Enter your phone number'**
  String get loginPhonePlaceholder;

  /// No description provided for @loginPwdLabel.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get loginPwdLabel;

  /// No description provided for @loginPwdPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Enter your password'**
  String get loginPwdPlaceholder;

  /// No description provided for @loginSmsLabel.
  ///
  /// In en, this message translates to:
  /// **'Verification Code'**
  String get loginSmsLabel;

  /// No description provided for @loginSmsPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'6-digit SMS code'**
  String get loginSmsPlaceholder;

  /// No description provided for @loginSendCode.
  ///
  /// In en, this message translates to:
  /// **'Send Code'**
  String get loginSendCode;

  /// No description provided for @loginResendCode.
  ///
  /// In en, this message translates to:
  /// **'Resend'**
  String get loginResendCode;

  /// No description provided for @loginRemember.
  ///
  /// In en, this message translates to:
  /// **'Stay signed in for 7 days'**
  String get loginRemember;

  /// No description provided for @loginForgot.
  ///
  /// In en, this message translates to:
  /// **'Forgot password?'**
  String get loginForgot;

  /// No description provided for @loginSubmit.
  ///
  /// In en, this message translates to:
  /// **'Log In'**
  String get loginSubmit;

  /// No description provided for @loginNoAccount.
  ///
  /// In en, this message translates to:
  /// **'No account yet?'**
  String get loginNoAccount;

  /// No description provided for @loginGoSignup.
  ///
  /// In en, this message translates to:
  /// **'Sign up now'**
  String get loginGoSignup;

  /// No description provided for @loginAgreementPrefix.
  ///
  /// In en, this message translates to:
  /// **'I have read and agree to the'**
  String get loginAgreementPrefix;

  /// No description provided for @loginAgreementTerms.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get loginAgreementTerms;

  /// No description provided for @loginAgreementAnd.
  ///
  /// In en, this message translates to:
  /// **'and'**
  String get loginAgreementAnd;

  /// No description provided for @loginAgreementPrivacy.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get loginAgreementPrivacy;

  /// No description provided for @homeSlogan.
  ///
  /// In en, this message translates to:
  /// **'Visa Made Simple'**
  String get homeSlogan;

  /// No description provided for @homeSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Multi-country visa support · Smart material checklist · Denial insurance · Express service'**
  String get homeSubtitle;

  /// No description provided for @homeCtaLogin.
  ///
  /// In en, this message translates to:
  /// **'Log In'**
  String get homeCtaLogin;

  /// No description provided for @homeCtaExplore.
  ///
  /// In en, this message translates to:
  /// **'Explore Countries'**
  String get homeCtaExplore;

  /// No description provided for @homeFeatureTitle.
  ///
  /// In en, this message translates to:
  /// **'Why Choose Us'**
  String get homeFeatureTitle;

  /// No description provided for @homeFeatureSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Turn the cumbersome visa process into 4 easy steps'**
  String get homeFeatureSubtitle;

  /// No description provided for @homeFeature1Title.
  ///
  /// In en, this message translates to:
  /// **'Auto Material Checklist'**
  String get homeFeature1Title;

  /// No description provided for @homeFeature1Desc.
  ///
  /// In en, this message translates to:
  /// **'Auto-generate required materials by destination — no missing or wrong submissions.'**
  String get homeFeature1Desc;

  /// No description provided for @homeFeature2Title.
  ///
  /// In en, this message translates to:
  /// **'Denial Insurance'**
  String get homeFeature2Title;

  /// No description provided for @homeFeature2Desc.
  ///
  /// In en, this message translates to:
  /// **'100% service fee refund if your visa is unfortunately denied.'**
  String get homeFeature2Desc;

  /// No description provided for @homeFeature3Title.
  ///
  /// In en, this message translates to:
  /// **'Template Library'**
  String get homeFeature3Title;

  /// No description provided for @homeFeature3Desc.
  ///
  /// In en, this message translates to:
  /// **'Employment proof, bank statements, invitation letters — one-click templates.'**
  String get homeFeature3Desc;

  /// No description provided for @homeFeature4Title.
  ///
  /// In en, this message translates to:
  /// **'Affiliate Program'**
  String get homeFeature4Title;

  /// No description provided for @homeFeature4Desc.
  ///
  /// In en, this message translates to:
  /// **'Refer a friend to apply — both of you get ¥50 coupon.'**
  String get homeFeature4Desc;

  /// No description provided for @registerTitle.
  ///
  /// In en, this message translates to:
  /// **'Create Your Account'**
  String get registerTitle;

  /// No description provided for @registerSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Sign up with phone + SMS code + password'**
  String get registerSubtitle;

  /// No description provided for @registerPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Phone Number'**
  String get registerPhoneLabel;

  /// No description provided for @registerPhonePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Enter your phone number'**
  String get registerPhonePlaceholder;

  /// No description provided for @registerSmsLabel.
  ///
  /// In en, this message translates to:
  /// **'SMS Code'**
  String get registerSmsLabel;

  /// No description provided for @registerSmsPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'6-digit verification code'**
  String get registerSmsPlaceholder;

  /// No description provided for @registerSendCode.
  ///
  /// In en, this message translates to:
  /// **'Send Code'**
  String get registerSendCode;

  /// No description provided for @registerResendIn.
  ///
  /// In en, this message translates to:
  /// **'Resend in'**
  String get registerResendIn;

  /// No description provided for @registerPwdLabel.
  ///
  /// In en, this message translates to:
  /// **'Password'**
  String get registerPwdLabel;

  /// No description provided for @registerPwdPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'8-32 chars, letters + digits'**
  String get registerPwdPlaceholder;

  /// No description provided for @registerConfirmLabel.
  ///
  /// In en, this message translates to:
  /// **'Confirm Password'**
  String get registerConfirmLabel;

  /// No description provided for @registerConfirmPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Re-enter your password'**
  String get registerConfirmPlaceholder;

  /// No description provided for @registerAgreementPrefix.
  ///
  /// In en, this message translates to:
  /// **'I have read and agree to the'**
  String get registerAgreementPrefix;

  /// No description provided for @registerAgreementTerms.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get registerAgreementTerms;

  /// No description provided for @registerAgreementAnd.
  ///
  /// In en, this message translates to:
  /// **'and'**
  String get registerAgreementAnd;

  /// No description provided for @registerAgreementPrivacy.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get registerAgreementPrivacy;

  /// No description provided for @registerSubmit.
  ///
  /// In en, this message translates to:
  /// **'Sign Up'**
  String get registerSubmit;

  /// No description provided for @registerHaveAccount.
  ///
  /// In en, this message translates to:
  /// **'Already have an account?'**
  String get registerHaveAccount;

  /// No description provided for @registerGoLogin.
  ///
  /// In en, this message translates to:
  /// **'Log in'**
  String get registerGoLogin;

  /// No description provided for @registerPwdHintShort.
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 8 characters'**
  String get registerPwdHintShort;

  /// No description provided for @registerPwdHintLong.
  ///
  /// In en, this message translates to:
  /// **'Password cannot exceed 32 characters'**
  String get registerPwdHintLong;

  /// No description provided for @registerPwdHintFormat.
  ///
  /// In en, this message translates to:
  /// **'Password must contain both letters and digits'**
  String get registerPwdHintFormat;

  /// No description provided for @registerPwdHintMismatch.
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match'**
  String get registerPwdHintMismatch;

  /// No description provided for @registerPwdHintOk.
  ///
  /// In en, this message translates to:
  /// **'Password strength: good'**
  String get registerPwdHintOk;

  /// No description provided for @registerPwdStrengthWeak.
  ///
  /// In en, this message translates to:
  /// **'Weak'**
  String get registerPwdStrengthWeak;

  /// No description provided for @registerPwdStrengthMedium.
  ///
  /// In en, this message translates to:
  /// **'Medium'**
  String get registerPwdStrengthMedium;

  /// No description provided for @registerPwdStrengthStrong.
  ///
  /// In en, this message translates to:
  /// **'Strong'**
  String get registerPwdStrengthStrong;

  /// No description provided for @materialsTitle.
  ///
  /// In en, this message translates to:
  /// **'Material Collection'**
  String get materialsTitle;

  /// No description provided for @materialsSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Upload passport, photos and documents. We auto-recognize via OCR.'**
  String get materialsSubtitle;

  /// No description provided for @materialsTabPhoto.
  ///
  /// In en, this message translates to:
  /// **'Photo'**
  String get materialsTabPhoto;

  /// No description provided for @materialsTabPdf.
  ///
  /// In en, this message translates to:
  /// **'Upload File'**
  String get materialsTabPdf;

  /// No description provided for @materialsTabVoice.
  ///
  /// In en, this message translates to:
  /// **'Voice'**
  String get materialsTabVoice;

  /// No description provided for @materialsUploadTitle.
  ///
  /// In en, this message translates to:
  /// **'Click or drag to upload'**
  String get materialsUploadTitle;

  /// No description provided for @materialsUploadDesc.
  ///
  /// In en, this message translates to:
  /// **'PDF, JPG, PNG, WebP — up to 10MB'**
  String get materialsUploadDesc;

  /// No description provided for @materialsFormatHint.
  ///
  /// In en, this message translates to:
  /// **'PDF / JPG / PNG / WebP'**
  String get materialsFormatHint;

  /// No description provided for @materialsSizeHint.
  ///
  /// In en, this message translates to:
  /// **'Max 10MB'**
  String get materialsSizeHint;

  /// No description provided for @materialsUploading.
  ///
  /// In en, this message translates to:
  /// **'Uploading'**
  String get materialsUploading;

  /// No description provided for @materialsUploadedOk.
  ///
  /// In en, this message translates to:
  /// **'Upload complete'**
  String get materialsUploadedOk;

  /// No description provided for @materialsCollectedCount.
  ///
  /// In en, this message translates to:
  /// **'Collected'**
  String get materialsCollectedCount;

  /// No description provided for @materialsEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No materials yet'**
  String get materialsEmptyTitle;

  /// No description provided for @materialsEmptyDesc.
  ///
  /// In en, this message translates to:
  /// **'Click above to upload your first document'**
  String get materialsEmptyDesc;

  /// No description provided for @materialsEmptyCta.
  ///
  /// In en, this message translates to:
  /// **'Upload Now'**
  String get materialsEmptyCta;

  /// No description provided for @materialsItemType.
  ///
  /// In en, this message translates to:
  /// **'Type'**
  String get materialsItemType;

  /// No description provided for @materialsTypePassport.
  ///
  /// In en, this message translates to:
  /// **'Passport'**
  String get materialsTypePassport;

  /// No description provided for @materialsTypePhoto.
  ///
  /// In en, this message translates to:
  /// **'Photo'**
  String get materialsTypePhoto;

  /// No description provided for @materialsTypeProof.
  ///
  /// In en, this message translates to:
  /// **'Proof'**
  String get materialsTypeProof;

  /// No description provided for @materialsTypeOther.
  ///
  /// In en, this message translates to:
  /// **'Other'**
  String get materialsTypeOther;

  /// No description provided for @materialsOcrDone.
  ///
  /// In en, this message translates to:
  /// **'OCR Done'**
  String get materialsOcrDone;

  /// No description provided for @materialsOcrProcessing.
  ///
  /// In en, this message translates to:
  /// **'OCR Processing'**
  String get materialsOcrProcessing;

  /// No description provided for @materialsOcrFailed.
  ///
  /// In en, this message translates to:
  /// **'OCR Failed'**
  String get materialsOcrFailed;

  /// No description provided for @materialsOcrPending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get materialsOcrPending;

  /// No description provided for @materialsValidateBtn.
  ///
  /// In en, this message translates to:
  /// **'Validate Materials'**
  String get materialsValidateBtn;

  /// No description provided for @materialsValidating.
  ///
  /// In en, this message translates to:
  /// **'Validating...'**
  String get materialsValidating;

  /// No description provided for @materialsContinueBtn.
  ///
  /// In en, this message translates to:
  /// **'Continue to Order'**
  String get materialsContinueBtn;

  /// No description provided for @errorsPhoneInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a valid phone number'**
  String get errorsPhoneInvalid;

  /// No description provided for @errorsPwdTooShort.
  ///
  /// In en, this message translates to:
  /// **'Password must be at least 8 characters'**
  String get errorsPwdTooShort;

  /// No description provided for @errorsCodeInvalid.
  ///
  /// In en, this message translates to:
  /// **'Please enter a 6-digit code'**
  String get errorsCodeInvalid;

  /// No description provided for @errorsNetwork.
  ///
  /// In en, this message translates to:
  /// **'Network error, please retry'**
  String get errorsNetwork;

  /// No description provided for @errorsAgreement.
  ///
  /// In en, this message translates to:
  /// **'Please agree to the terms first'**
  String get errorsAgreement;

  /// No description provided for @errorsFileTooBig.
  ///
  /// In en, this message translates to:
  /// **'File too large (max 10MB)'**
  String get errorsFileTooBig;

  /// No description provided for @errorsFileType.
  ///
  /// In en, this message translates to:
  /// **'Unsupported file type'**
  String get errorsFileType;

  /// No description provided for @toastLoginSuccess.
  ///
  /// In en, this message translates to:
  /// **'Logged in successfully'**
  String get toastLoginSuccess;

  /// No description provided for @toastLoginFail.
  ///
  /// In en, this message translates to:
  /// **'Login failed, please check your credentials'**
  String get toastLoginFail;

  /// No description provided for @toastCodeSent.
  ///
  /// In en, this message translates to:
  /// **'Code sent'**
  String get toastCodeSent;

  /// No description provided for @toastCodeSendSuccess.
  ///
  /// In en, this message translates to:
  /// **'Verification code sent'**
  String get toastCodeSendSuccess;

  /// No description provided for @toastRegisterSuccess.
  ///
  /// In en, this message translates to:
  /// **'Account created, please log in'**
  String get toastRegisterSuccess;

  /// No description provided for @toastRegisterFail.
  ///
  /// In en, this message translates to:
  /// **'Registration failed, please try again'**
  String get toastRegisterFail;

  /// No description provided for @toastMaterialUploaded.
  ///
  /// In en, this message translates to:
  /// **'Material uploaded'**
  String get toastMaterialUploaded;

  /// No description provided for @toastMaterialDeleted.
  ///
  /// In en, this message translates to:
  /// **'Material deleted'**
  String get toastMaterialDeleted;

  /// No description provided for @toastMaterialsValidated.
  ///
  /// In en, this message translates to:
  /// **'Materials validated'**
  String get toastMaterialsValidated;

  /// No description provided for @phoneCountryCn.
  ///
  /// In en, this message translates to:
  /// **'China +86'**
  String get phoneCountryCn;

  /// No description provided for @phoneCountryId.
  ///
  /// In en, this message translates to:
  /// **'Indonesia +62'**
  String get phoneCountryId;

  /// No description provided for @phoneCountryVn.
  ///
  /// In en, this message translates to:
  /// **'Vietnam +84'**
  String get phoneCountryVn;

  /// No description provided for @phoneCountryPh.
  ///
  /// In en, this message translates to:
  /// **'Philippines +63'**
  String get phoneCountryPh;

  /// No description provided for @commonRetry.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get commonRetry;

  /// No description provided for @commonNetworkError.
  ///
  /// In en, this message translates to:
  /// **'Network error, please retry'**
  String get commonNetworkError;

  /// No description provided for @commonAppName.
  ///
  /// In en, this message translates to:
  /// **'Visa Helper'**
  String get commonAppName;

  /// No description provided for @destTitle.
  ///
  /// In en, this message translates to:
  /// **'Choose Your Destination'**
  String get destTitle;

  /// No description provided for @destSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Select a country to start your visa application'**
  String get destSubtitle;

  /// No description provided for @destTourism.
  ///
  /// In en, this message translates to:
  /// **'Tourism'**
  String get destTourism;

  /// No description provided for @destStudent.
  ///
  /// In en, this message translates to:
  /// **'Student'**
  String get destStudent;

  /// No description provided for @destComingSoon.
  ///
  /// In en, this message translates to:
  /// **'Coming Soon'**
  String get destComingSoon;

  /// No description provided for @destApplyNow.
  ///
  /// In en, this message translates to:
  /// **'Apply Now'**
  String get destApplyNow;

  /// No description provided for @languageZh.
  ///
  /// In en, this message translates to:
  /// **'简体中文'**
  String get languageZh;

  /// No description provided for @languageEn.
  ///
  /// In en, this message translates to:
  /// **'English'**
  String get languageEn;

  /// No description provided for @languageId.
  ///
  /// In en, this message translates to:
  /// **'Bahasa Indonesia'**
  String get languageId;

  /// No description provided for @languageVi.
  ///
  /// In en, this message translates to:
  /// **'Tiếng Việt'**
  String get languageVi;

  /// No description provided for @profilePageTitle.
  ///
  /// In en, this message translates to:
  /// **'My Profile'**
  String get profilePageTitle;

  /// No description provided for @profilePageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Manage your account'**
  String get profilePageSubtitle;

  /// No description provided for @profileUserId.
  ///
  /// In en, this message translates to:
  /// **'User ID'**
  String get profileUserId;

  /// No description provided for @profileLanguagePref.
  ///
  /// In en, this message translates to:
  /// **'Language'**
  String get profileLanguagePref;

  /// No description provided for @profileRegisterTime.
  ///
  /// In en, this message translates to:
  /// **'Member Since'**
  String get profileRegisterTime;

  /// No description provided for @profileStatus.
  ///
  /// In en, this message translates to:
  /// **'Status'**
  String get profileStatus;

  /// No description provided for @profileStatusActive.
  ///
  /// In en, this message translates to:
  /// **'Active'**
  String get profileStatusActive;

  /// No description provided for @profileLoggedOut.
  ///
  /// In en, this message translates to:
  /// **'Not logged in'**
  String get profileLoggedOut;

  /// No description provided for @profileGoLogin.
  ///
  /// In en, this message translates to:
  /// **'Log in'**
  String get profileGoLogin;

  /// No description provided for @profileForgotPwd.
  ///
  /// In en, this message translates to:
  /// **'Reset Password'**
  String get profileForgotPwd;

  /// No description provided for @profileAgreement.
  ///
  /// In en, this message translates to:
  /// **'Terms & Privacy'**
  String get profileAgreement;

  /// No description provided for @toastLogoutSuccess.
  ///
  /// In en, this message translates to:
  /// **'Logged out successfully'**
  String get toastLogoutSuccess;

  /// No description provided for @orderPageTitle.
  ///
  /// In en, this message translates to:
  /// **'My Orders'**
  String get orderPageTitle;

  /// No description provided for @orderPageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Track all your visa applications'**
  String get orderPageSubtitle;

  /// No description provided for @orderTabAll.
  ///
  /// In en, this message translates to:
  /// **'All'**
  String get orderTabAll;

  /// No description provided for @orderTabPendingPayment.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get orderTabPendingPayment;

  /// No description provided for @orderTabPaid.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get orderTabPaid;

  /// No description provided for @orderTabReviewing.
  ///
  /// In en, this message translates to:
  /// **'Reviewing'**
  String get orderTabReviewing;

  /// No description provided for @orderTabApproved.
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get orderTabApproved;

  /// No description provided for @orderTabRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get orderTabRejected;

  /// No description provided for @orderLoading.
  ///
  /// In en, this message translates to:
  /// **'Loading orders...'**
  String get orderLoading;

  /// No description provided for @orderEmptyTitle.
  ///
  /// In en, this message translates to:
  /// **'No orders yet'**
  String get orderEmptyTitle;

  /// No description provided for @orderEmptyDesc.
  ///
  /// In en, this message translates to:
  /// **'Your orders will appear here'**
  String get orderEmptyDesc;

  /// No description provided for @orderEmptyAction.
  ///
  /// In en, this message translates to:
  /// **'Go apply'**
  String get orderEmptyAction;

  /// No description provided for @orderItemAmount.
  ///
  /// In en, this message translates to:
  /// **'Amount'**
  String get orderItemAmount;

  /// No description provided for @orderItemVisaType.
  ///
  /// In en, this message translates to:
  /// **'Visa Type'**
  String get orderItemVisaType;

  /// No description provided for @orderItemVisaTourism.
  ///
  /// In en, this message translates to:
  /// **'Tourism'**
  String get orderItemVisaTourism;

  /// No description provided for @orderItemVisaStudent.
  ///
  /// In en, this message translates to:
  /// **'Student'**
  String get orderItemVisaStudent;

  /// No description provided for @orderItemCreated.
  ///
  /// In en, this message translates to:
  /// **'Created'**
  String get orderItemCreated;

  /// No description provided for @orderItemPayNow.
  ///
  /// In en, this message translates to:
  /// **'Pay Now'**
  String get orderItemPayNow;

  /// No description provided for @orderItemViewDetail.
  ///
  /// In en, this message translates to:
  /// **'View Detail'**
  String get orderItemViewDetail;

  /// No description provided for @orderRejectReasonLabel.
  ///
  /// In en, this message translates to:
  /// **'Rejection Reason'**
  String get orderRejectReasonLabel;

  /// No description provided for @orderLoadFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to load orders'**
  String get orderLoadFailed;

  /// No description provided for @orderNotLoggedIn.
  ///
  /// In en, this message translates to:
  /// **'Please log in first'**
  String get orderNotLoggedIn;

  /// No description provided for @orderGoLogin.
  ///
  /// In en, this message translates to:
  /// **'Log In'**
  String get orderGoLogin;

  /// No description provided for @paymentPageTitle.
  ///
  /// In en, this message translates to:
  /// **'Payment'**
  String get paymentPageTitle;

  /// No description provided for @paymentPageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Scan QR code to pay'**
  String get paymentPageSubtitle;

  /// No description provided for @paymentOrderLabel.
  ///
  /// In en, this message translates to:
  /// **'Order'**
  String get paymentOrderLabel;

  /// No description provided for @paymentAmountLabel.
  ///
  /// In en, this message translates to:
  /// **'Amount'**
  String get paymentAmountLabel;

  /// No description provided for @paymentQrHint.
  ///
  /// In en, this message translates to:
  /// **'Open WeChat → Scan'**
  String get paymentQrHint;

  /// No description provided for @paymentQrLoading.
  ///
  /// In en, this message translates to:
  /// **'Generating QR code...'**
  String get paymentQrLoading;

  /// No description provided for @paymentQrExpired.
  ///
  /// In en, this message translates to:
  /// **'QR Code Expired'**
  String get paymentQrExpired;

  /// No description provided for @paymentStatusPending.
  ///
  /// In en, this message translates to:
  /// **'Pending'**
  String get paymentStatusPending;

  /// No description provided for @paymentStatusPaid.
  ///
  /// In en, this message translates to:
  /// **'Paid'**
  String get paymentStatusPaid;

  /// No description provided for @paymentStatusFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed'**
  String get paymentStatusFailed;

  /// No description provided for @paymentPollingLabel.
  ///
  /// In en, this message translates to:
  /// **'Polling'**
  String get paymentPollingLabel;

  /// No description provided for @paymentPollingUnit.
  ///
  /// In en, this message translates to:
  /// **'times'**
  String get paymentPollingUnit;

  /// No description provided for @paymentPollNow.
  ///
  /// In en, this message translates to:
  /// **'Polling now'**
  String get paymentPollNow;

  /// No description provided for @paymentExpireLabel.
  ///
  /// In en, this message translates to:
  /// **'Expires in'**
  String get paymentExpireLabel;

  /// No description provided for @paymentExpireUnit.
  ///
  /// In en, this message translates to:
  /// **'min'**
  String get paymentExpireUnit;

  /// No description provided for @paymentBackBtn.
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get paymentBackBtn;

  /// No description provided for @paymentBackSuccess.
  ///
  /// In en, this message translates to:
  /// **'Payment successful!'**
  String get paymentBackSuccess;

  /// No description provided for @paymentCreateFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to create payment'**
  String get paymentCreateFailed;

  /// No description provided for @paymentPollFailed.
  ///
  /// In en, this message translates to:
  /// **'Failed to check payment status'**
  String get paymentPollFailed;

  /// No description provided for @forgotPageTitle.
  ///
  /// In en, this message translates to:
  /// **'Reset Password'**
  String get forgotPageTitle;

  /// No description provided for @forgotPageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Enter your phone and we\'ll send you a reset code'**
  String get forgotPageSubtitle;

  /// No description provided for @forgotPhoneLabel.
  ///
  /// In en, this message translates to:
  /// **'Phone Number'**
  String get forgotPhoneLabel;

  /// No description provided for @forgotPhonePlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Enter your phone number'**
  String get forgotPhonePlaceholder;

  /// No description provided for @forgotSmsLabel.
  ///
  /// In en, this message translates to:
  /// **'SMS Code'**
  String get forgotSmsLabel;

  /// No description provided for @forgotSmsPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'6-digit code'**
  String get forgotSmsPlaceholder;

  /// No description provided for @forgotSendCode.
  ///
  /// In en, this message translates to:
  /// **'Send Code'**
  String get forgotSendCode;

  /// No description provided for @forgotResendCode.
  ///
  /// In en, this message translates to:
  /// **'Resend'**
  String get forgotResendCode;

  /// No description provided for @forgotNewPwdLabel.
  ///
  /// In en, this message translates to:
  /// **'New Password'**
  String get forgotNewPwdLabel;

  /// No description provided for @forgotNewPwdPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'8+ characters'**
  String get forgotNewPwdPlaceholder;

  /// No description provided for @forgotConfirmPwdLabel.
  ///
  /// In en, this message translates to:
  /// **'Confirm Password'**
  String get forgotConfirmPwdLabel;

  /// No description provided for @forgotConfirmPwdPlaceholder.
  ///
  /// In en, this message translates to:
  /// **'Re-enter new password'**
  String get forgotConfirmPwdPlaceholder;

  /// No description provided for @forgotSubmit.
  ///
  /// In en, this message translates to:
  /// **'Reset Password'**
  String get forgotSubmit;

  /// No description provided for @forgotSubmitting.
  ///
  /// In en, this message translates to:
  /// **'Resetting...'**
  String get forgotSubmitting;

  /// No description provided for @forgotBackLogin.
  ///
  /// In en, this message translates to:
  /// **'Back to Log In'**
  String get forgotBackLogin;

  /// No description provided for @forgotSuccessTitle.
  ///
  /// In en, this message translates to:
  /// **'Password Reset!'**
  String get forgotSuccessTitle;

  /// No description provided for @forgotSuccessDesc.
  ///
  /// In en, this message translates to:
  /// **'Your password has been updated successfully'**
  String get forgotSuccessDesc;

  /// No description provided for @forgotGoLogin.
  ///
  /// In en, this message translates to:
  /// **'Log In Now'**
  String get forgotGoLogin;

  /// No description provided for @errorsPwdMismatch.
  ///
  /// In en, this message translates to:
  /// **'Passwords do not match'**
  String get errorsPwdMismatch;

  /// No description provided for @agreementPageTitle.
  ///
  /// In en, this message translates to:
  /// **'Legal'**
  String get agreementPageTitle;

  /// No description provided for @agreementPageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service & Privacy Policy'**
  String get agreementPageSubtitle;

  /// No description provided for @agreementTabTerms.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get agreementTabTerms;

  /// No description provided for @agreementTabPrivacy.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get agreementTabPrivacy;

  /// No description provided for @agreementTermsTitle.
  ///
  /// In en, this message translates to:
  /// **'Terms of Service'**
  String get agreementTermsTitle;

  /// No description provided for @agreementTermsEffective.
  ///
  /// In en, this message translates to:
  /// **'Effective: January 1, 2026'**
  String get agreementTermsEffective;

  /// No description provided for @agreementTermsSection1Title.
  ///
  /// In en, this message translates to:
  /// **'1. Service Scope'**
  String get agreementTermsSection1Title;

  /// No description provided for @agreementTermsSection1Body.
  ///
  /// In en, this message translates to:
  /// **'Visa Helper provides visa application advisory and document preparation services. We act as an intermediary between users and embassies/consulates and do not guarantee visa approval. Visa decisions are made solely by the respective authorities.'**
  String get agreementTermsSection1Body;

  /// No description provided for @agreementTermsSection2Title.
  ///
  /// In en, this message translates to:
  /// **'2. User Responsibilities'**
  String get agreementTermsSection2Title;

  /// No description provided for @agreementTermsSection2Body.
  ///
  /// In en, this message translates to:
  /// **'Users must ensure all submitted materials are authentic and complete. Providing false information may result in application rejection, fees forfeited, or legal liability.'**
  String get agreementTermsSection2Body;

  /// No description provided for @agreementTermsSection3Title.
  ///
  /// In en, this message translates to:
  /// **'3. Service Fees'**
  String get agreementTermsSection3Title;

  /// No description provided for @agreementTermsSection3Body.
  ///
  /// In en, this message translates to:
  /// **'Service fees are charged for document preparation and advisory services, not for visa approval. Fees are non-refundable unless otherwise specified in the denial insurance policy.'**
  String get agreementTermsSection3Body;

  /// No description provided for @agreementTermsSection4Title.
  ///
  /// In en, this message translates to:
  /// **'4. Disclaimer'**
  String get agreementTermsSection4Title;

  /// No description provided for @agreementTermsSection4Body.
  ///
  /// In en, this message translates to:
  /// **'Visa Helper is not liable for visa denial, processing delays, or any consequences arising from user-provided false information or incomplete materials.'**
  String get agreementTermsSection4Body;

  /// No description provided for @agreementPrivacyTitle.
  ///
  /// In en, this message translates to:
  /// **'Privacy Policy'**
  String get agreementPrivacyTitle;

  /// No description provided for @agreementPrivacyEffective.
  ///
  /// In en, this message translates to:
  /// **'Effective: January 1, 2026'**
  String get agreementPrivacyEffective;

  /// No description provided for @agreementPrivacySection1Title.
  ///
  /// In en, this message translates to:
  /// **'1. Data We Collect'**
  String get agreementPrivacySection1Title;

  /// No description provided for @agreementPrivacySection1Body.
  ///
  /// In en, this message translates to:
  /// **'We collect personal information (name, passport, phone) and materials (passport scan, photos) solely for visa application purposes. Data is encrypted in transit and stored securely.'**
  String get agreementPrivacySection1Body;

  /// No description provided for @agreementPrivacySection2Title.
  ///
  /// In en, this message translates to:
  /// **'2. Data Usage'**
  String get agreementPrivacySection2Title;

  /// No description provided for @agreementPrivacySection2Body.
  ///
  /// In en, this message translates to:
  /// **'Your data is used exclusively for: generating application materials, communicating with you about your application status, and improving our services. We do not sell or share your data with third parties for marketing.'**
  String get agreementPrivacySection2Body;

  /// No description provided for @agreementPrivacySection3Title.
  ///
  /// In en, this message translates to:
  /// **'3. Data Retention'**
  String get agreementPrivacySection3Title;

  /// No description provided for @agreementPrivacySection3Body.
  ///
  /// In en, this message translates to:
  /// **'Application data is retained for 24 months after service completion, then deleted. You may request deletion at any time by contacting support@visahelper.com.'**
  String get agreementPrivacySection3Body;

  /// No description provided for @agreementPrivacySection4Title.
  ///
  /// In en, this message translates to:
  /// **'4. Security'**
  String get agreementPrivacySection4Title;

  /// No description provided for @agreementPrivacySection4Body.
  ///
  /// In en, this message translates to:
  /// **'We use AES-256 encryption for stored data and TLS 1.3 for data in transit. Access is restricted to authorized personnel and audited quarterly.'**
  String get agreementPrivacySection4Body;

  /// No description provided for @orderdetailPageTitle.
  ///
  /// In en, this message translates to:
  /// **'Order Detail'**
  String get orderdetailPageTitle;

  /// No description provided for @orderdetailPageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Track your visa application'**
  String get orderdetailPageSubtitle;

  /// No description provided for @orderdetailOrderNoLabel.
  ///
  /// In en, this message translates to:
  /// **'Order No.'**
  String get orderdetailOrderNoLabel;

  /// No description provided for @orderdetailUpdatedAtLabel.
  ///
  /// In en, this message translates to:
  /// **'Updated at'**
  String get orderdetailUpdatedAtLabel;

  /// No description provided for @orderdetailSectionTimeline.
  ///
  /// In en, this message translates to:
  /// **'Application Timeline'**
  String get orderdetailSectionTimeline;

  /// No description provided for @orderdetailSectionPassport.
  ///
  /// In en, this message translates to:
  /// **'Passport Info'**
  String get orderdetailSectionPassport;

  /// No description provided for @orderdetailFieldName.
  ///
  /// In en, this message translates to:
  /// **'Passport Name'**
  String get orderdetailFieldName;

  /// No description provided for @orderdetailFieldPassportNo.
  ///
  /// In en, this message translates to:
  /// **'Passport No.'**
  String get orderdetailFieldPassportNo;

  /// No description provided for @orderdetailStepCreated.
  ///
  /// In en, this message translates to:
  /// **'Order Created'**
  String get orderdetailStepCreated;

  /// No description provided for @orderdetailStepSubmitted.
  ///
  /// In en, this message translates to:
  /// **'Submitted'**
  String get orderdetailStepSubmitted;

  /// No description provided for @orderdetailStepReviewing.
  ///
  /// In en, this message translates to:
  /// **'Under Review'**
  String get orderdetailStepReviewing;

  /// No description provided for @orderdetailStepApproved.
  ///
  /// In en, this message translates to:
  /// **'Approved'**
  String get orderdetailStepApproved;

  /// No description provided for @orderdetailStepRejected.
  ///
  /// In en, this message translates to:
  /// **'Rejected'**
  String get orderdetailStepRejected;

  /// No description provided for @orderdetailRetryBtn.
  ///
  /// In en, this message translates to:
  /// **'Retry'**
  String get orderdetailRetryBtn;

  /// No description provided for @orderdetailLogoutBtn.
  ///
  /// In en, this message translates to:
  /// **'Log Out'**
  String get orderdetailLogoutBtn;

  /// No description provided for @orderdetailWsConnected.
  ///
  /// In en, this message translates to:
  /// **'Live'**
  String get orderdetailWsConnected;

  /// No description provided for @orderdetailWsConnecting.
  ///
  /// In en, this message translates to:
  /// **'Connecting'**
  String get orderdetailWsConnecting;

  /// No description provided for @orderdetailPollingLabel.
  ///
  /// In en, this message translates to:
  /// **'Polling'**
  String get orderdetailPollingLabel;

  /// No description provided for @orderdetailPollingUnit.
  ///
  /// In en, this message translates to:
  /// **'s'**
  String get orderdetailPollingUnit;

  /// No description provided for @ordernewPageTitle.
  ///
  /// In en, this message translates to:
  /// **'Visa Application'**
  String get ordernewPageTitle;

  /// No description provided for @ordernewPageSubtitle.
  ///
  /// In en, this message translates to:
  /// **'Complete your application form'**
  String get ordernewPageSubtitle;

  /// No description provided for @ordernewDestLabel.
  ///
  /// In en, this message translates to:
  /// **'Destination'**
  String get ordernewDestLabel;

  /// No description provided for @ordernewOcrPrefilled.
  ///
  /// In en, this message translates to:
  /// **'OCR prefilled'**
  String get ordernewOcrPrefilled;

  /// No description provided for @ordernewBtnBack.
  ///
  /// In en, this message translates to:
  /// **'Back'**
  String get ordernewBtnBack;

  /// No description provided for @ordernewTabBasic.
  ///
  /// In en, this message translates to:
  /// **'Basic'**
  String get ordernewTabBasic;

  /// No description provided for @ordernewTabTravel.
  ///
  /// In en, this message translates to:
  /// **'Travel'**
  String get ordernewTabTravel;

  /// No description provided for @ordernewTabEmergency.
  ///
  /// In en, this message translates to:
  /// **'Emergency'**
  String get ordernewTabEmergency;

  /// No description provided for @ordernewSectionBasic.
  ///
  /// In en, this message translates to:
  /// **'Basic Information'**
  String get ordernewSectionBasic;

  /// No description provided for @ordernewSectionTravel.
  ///
  /// In en, this message translates to:
  /// **'Travel Details'**
  String get ordernewSectionTravel;

  /// No description provided for @ordernewSectionEmergency.
  ///
  /// In en, this message translates to:
  /// **'Emergency Contact'**
  String get ordernewSectionEmergency;

  /// No description provided for @ordernewFieldSurname.
  ///
  /// In en, this message translates to:
  /// **'Surname'**
  String get ordernewFieldSurname;

  /// No description provided for @ordernewFieldGiven.
  ///
  /// In en, this message translates to:
  /// **'Given Name'**
  String get ordernewFieldGiven;

  /// No description provided for @ordernewFieldDob.
  ///
  /// In en, this message translates to:
  /// **'Date of Birth'**
  String get ordernewFieldDob;

  /// No description provided for @ordernewFieldNationality.
  ///
  /// In en, this message translates to:
  /// **'Nationality'**
  String get ordernewFieldNationality;

  /// No description provided for @ordernewFieldPassportNo.
  ///
  /// In en, this message translates to:
  /// **'Passport Number'**
  String get ordernewFieldPassportNo;

  /// No description provided for @ordernewFieldPassportExp.
  ///
  /// In en, this message translates to:
  /// **'Passport Expiry'**
  String get ordernewFieldPassportExp;

  /// No description provided for @ordernewFieldArrival.
  ///
  /// In en, this message translates to:
  /// **'Arrival Date'**
  String get ordernewFieldArrival;

  /// No description provided for @ordernewFieldDeparture.
  ///
  /// In en, this message translates to:
  /// **'Departure Date'**
  String get ordernewFieldDeparture;

  /// No description provided for @ordernewFieldPurpose.
  ///
  /// In en, this message translates to:
  /// **'Purpose of Visit'**
  String get ordernewFieldPurpose;

  /// No description provided for @ordernewFieldEmergencyName.
  ///
  /// In en, this message translates to:
  /// **'Contact Name'**
  String get ordernewFieldEmergencyName;

  /// No description provided for @ordernewFieldEmergencyPhone.
  ///
  /// In en, this message translates to:
  /// **'Contact Phone'**
  String get ordernewFieldEmergencyPhone;

  /// No description provided for @ordernewFieldEmergencyRel.
  ///
  /// In en, this message translates to:
  /// **'Relationship'**
  String get ordernewFieldEmergencyRel;

  /// No description provided for @ordernewSubmit.
  ///
  /// In en, this message translates to:
  /// **'Submit Application'**
  String get ordernewSubmit;

  /// No description provided for @ordernewSubmitting.
  ///
  /// In en, this message translates to:
  /// **'Submitting...'**
  String get ordernewSubmitting;
}

class _AppLocalizationsDelegate
    extends LocalizationsDelegate<AppLocalizations> {
  const _AppLocalizationsDelegate();

  @override
  Future<AppLocalizations> load(Locale locale) {
    return SynchronousFuture<AppLocalizations>(lookupAppLocalizations(locale));
  }

  @override
  bool isSupported(Locale locale) =>
      <String>['en', 'id', 'vi', 'zh'].contains(locale.languageCode);

  @override
  bool shouldReload(_AppLocalizationsDelegate old) => false;
}

AppLocalizations lookupAppLocalizations(Locale locale) {
  // Lookup logic when only language code is specified.
  switch (locale.languageCode) {
    case 'en':
      return AppLocalizationsEn();
    case 'id':
      return AppLocalizationsId();
    case 'vi':
      return AppLocalizationsVi();
    case 'zh':
      return AppLocalizationsZh();
  }

  throw FlutterError(
      'AppLocalizations.delegate failed to load unsupported locale "$locale". This is likely '
      'an issue with the localizations generation tool. Please file an issue '
      'on GitHub with a reproducible sample app and the gen-l10n configuration '
      'that was used.');
}
