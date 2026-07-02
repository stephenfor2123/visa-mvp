// Visa iOS app entry point — W32 routes (16 pages).
//
// Initializes Flutter, configures 4-locale l10n (en/zh/id/vi) via
// flutter_localizations + AppLocalizations (generated from lib/l10n/*.arb).
//
// Locale resolution order (W34):
//   1. ?lang= URL param (W9-1 screenshot hook) — explicit override
//   2. Device locale (PlatformDispatcher.locale) — matches zh/en/id/vi
//   3. Fallback to zh (matches our primary market, China outbound travel)
//
// Routing (Navigator 1.0, name-based):
//   /                  → HomePage
//   /login             → LoginPage              (W32 account login)
//   /register          → RegisterPage           (W32 username+email+password)
//   /forgot            → ForgotPage             (W32 reset by account)
//   /apply             → ApplyPage              (W32 4-step wizard)
//   /diagnose          → DiagnosePage           (W31/W32 risk pre-check)
//   /resources         → ResourcesPage          (RAG Q&A)
//   /passport-upload   → PassportUploadPage     (W32 OCR flow)
//   /contact           → ContactPage
//   /destinations      → DestinationsPage       (W32 hero 5 + schengen 26)
//   /materials         → MaterialsPage
//   /materials-upload  → MaterialsUploadPage
//   /profile           → ProfilePage
//   /orders            → OrdersPage
//   /order-detail      → OrderDetailPage
//   /order-form        → OrderFormPage
//   /payment           → PaymentPage
//   /agreement         → AgreementPage

import 'dart:io' show Platform;

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';

import 'l10n/generated/app_localizations.dart';
import 'pages/agreement_page.dart';
import 'pages/apply_page.dart';
import 'pages/contact_page.dart';
import 'pages/destinations_page.dart';
import 'pages/diagnose_page.dart';
import 'pages/forgot_page.dart';
import 'pages/home_page.dart';
import 'pages/login_page.dart';
import 'pages/materials_page.dart';
import 'pages/materials_upload_page.dart';
import 'pages/order_detail_page.dart';
import 'pages/order_form_page.dart';
import 'pages/orders_page.dart';
import 'pages/passport_upload_page.dart';
import 'pages/payment_page.dart';
import 'pages/profile_page.dart';
import 'pages/register_page.dart';
import 'pages/resources_page.dart';
import 'services/auth_service.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();
  // W35: testing convenience — ?auto_login=user:pass auto-fills auth state.
  final params = Uri.base.queryParameters;
  final al = params['auto_login'];
  if (al != null && al.contains(':')) {
    final parts = al.split(':');
    if (parts.length == 2) {
      try {
        await AuthService().loginByAccount(account: parts[0], password: parts[1]);
      } catch (_) {/* ignore — fall through to normal app */}
    }
  }
  runApp(const VisaIosApp());
}

/// Resolve the best supported locale for the current device.
///
/// W34: prefer device locale over hardcoded 'zh'. Returns null if no
/// supported language code matches and no usable device locale exists.
Locale? _resolveDeviceLocale(Iterable<Locale> supported) {
  // Skip on web for now — flutter web doesn't expose Platform.localeName
  // portably, and the URL ?lang= hook already covers the screenshot flow.
  if (kIsWeb) return null;
  try {
    final tag = Platform.localeName; // e.g. "zh_CN", "en_US", "id_ID", "vi_VN"
    final code = tag.split(RegExp('[-_]')).first.toLowerCase();
    for (final l in supported) {
      if (l.languageCode == code) return l;
    }
  } catch (_) {
    // Platform.localeName may throw in tests / on some hosts.
  }
  return null;
}

class VisaIosApp extends StatelessWidget {
  const VisaIosApp({super.key});

  @override
  Widget build(BuildContext context) {
    final params = Uri.base.queryParameters;
    final lang = params['lang'];
    final page = params['page'];
    final country = params['country']; // W35: testing hook for deep-link into Apply step 2
    final supportedLocales = AppLocalizations.supportedLocales;
    Locale? initialLocale;
    if (lang != null) {
      for (final l in supportedLocales) {
        if (l.languageCode == lang) {
          initialLocale = l;
          break;
        }
      }
    }
    // No URL override → follow device locale (W34).
    initialLocale ??= _resolveDeviceLocale(supportedLocales);
    String initialRoute = AppRoutes.home;
    if (page != null) {
      switch (page) {
        case 'home': initialRoute = AppRoutes.home; break;
        case 'login': initialRoute = AppRoutes.login; break;
        case 'register': initialRoute = AppRoutes.register; break;
        case 'forgot': initialRoute = AppRoutes.forgot; break;
        case 'apply': initialRoute = AppRoutes.apply; break;
        case 'diagnose': initialRoute = AppRoutes.diagnose; break;
        case 'resources': initialRoute = AppRoutes.resources; break;
        case 'passport-upload': initialRoute = AppRoutes.passportUpload; break;
        case 'contact': initialRoute = AppRoutes.contact; break;
        case 'materials': initialRoute = AppRoutes.materials; break;
        case 'materials-upload': initialRoute = AppRoutes.materialsUpload; break;
        case 'profile': initialRoute = AppRoutes.profile; break;
        case 'orders': initialRoute = AppRoutes.orders; break;
        case 'order-detail': initialRoute = AppRoutes.orderDetail; break;
        case 'order-form': initialRoute = AppRoutes.orderForm; break;
        case 'payment': initialRoute = AppRoutes.payment; break;
        case 'agreement': initialRoute = AppRoutes.agreement; break;
        case 'destinations': initialRoute = AppRoutes.destinations; break;
      }
    }
    return MaterialApp(
      title: 'Htex',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF3B6EF5),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: initialLocale, // null → Flutter picks best match from supported
      initialRoute: initialRoute,
      onGenerateRoute: AppRoutes.generateRoute,
    );
  }
}

class AppRoutes {
  static const String home = '/';
  static const String login = '/login';
  static const String register = '/register';
  static const String forgot = '/forgot';
  static const String apply = '/apply';
  static const String diagnose = '/diagnose';
  static const String resources = '/resources';
  static const String passportUpload = '/passport-upload';
  static const String contact = '/contact';
  static const String materials = '/materials';
  static const String materialsUpload = '/materials-upload';
  static const String profile = '/profile';
  static const String orders = '/orders';
  static const String orderDetail = '/order-detail';
  static const String orderForm = '/order-form';
  static const String payment = '/payment';
  static const String agreement = '/agreement';
  static const String destinations = '/destinations';

  static Route<dynamic> generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case home:
        return MaterialPageRoute(builder: (_) => const HomePage());
      case login:
        return MaterialPageRoute(builder: (_) => const LoginPage());
      case register:
        return MaterialPageRoute(builder: (_) => const RegisterPage());
      case forgot:
        return MaterialPageRoute(builder: (_) => const ForgotPage());
      case apply:
        final cc = settings.arguments as String?;
        return MaterialPageRoute(builder: (_) => ApplyPage(initialCountryCode: cc));
      case diagnose:
        return MaterialPageRoute(builder: (_) => const DiagnosePage());
      case resources:
        return MaterialPageRoute(builder: (_) => const ResourcesPage());
      case passportUpload:
        return MaterialPageRoute(builder: (_) => const PassportUploadPage());
      case contact:
        return MaterialPageRoute(builder: (_) => const ContactPage());
      case materials:
        return MaterialPageRoute(builder: (_) => const MaterialsPage());
      case materialsUpload:
        final orderNo = settings.arguments as String?;
        return MaterialPageRoute(builder: (_) => MaterialsUploadPage(orderNo: orderNo));
      case profile:
        return MaterialPageRoute(builder: (_) => const ProfilePage());
      case orders:
        return MaterialPageRoute(builder: (_) => const OrdersPage());
      case orderDetail:
        final orderNo = settings.arguments as String?;
        return MaterialPageRoute(builder: (_) => OrderDetailPage(orderNo: orderNo));
      case orderForm:
        final orderNo = settings.arguments as String?;
        return MaterialPageRoute(builder: (_) => OrderFormPage(orderNo: orderNo));
      case payment:
        final orderNo = settings.arguments as String?;
        return MaterialPageRoute(builder: (_) => PaymentPage(orderNo: orderNo));
      case agreement:
        return MaterialPageRoute(builder: (_) => const AgreementPage());
      case destinations:
        return MaterialPageRoute(builder: (_) => const DestinationsPage());
      default:
        return MaterialPageRoute(builder: (_) => const HomePage());
    }
  }
}