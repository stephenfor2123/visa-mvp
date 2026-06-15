// Visa iOS app entry point — W8-W15 pages port.
//
// Initializes Flutter, configures 4-locale l10n (en/zh/id/vi) via
// flutter_localizations + AppLocalizations (generated from lib/l10n/*.arb).
//
// Routing (Navigator 1.0, no extra deps):
//   /            → HomePage
//   /login       → LoginPage
//   /register    → RegisterPage
//   /materials   → MaterialsPage
//   /destinations→ DestinationsPage    (W13)
//   /profile     → ProfilePage         (W13)
//   /orders      → OrdersPage          (W13)
//   /payment     → PaymentPage         (W13)
//   /forgot      → ForgotPage          (W13)
//   /agreement   → AgreementPage      (W13)
//   /order-detail→ OrderDetailPage     (W14)
//   /order-form  → OrderFormPage       (W14)
//   /materials-upload → MaterialsUploadPage (W14)

import 'package:flutter/material.dart';

import 'l10n/generated/app_localizations.dart';
import 'pages/home_page.dart';
import 'pages/login_page.dart';
import 'pages/register_page.dart';
import 'pages/materials_page.dart';
import 'pages/destinations_page.dart';
import 'pages/profile_page.dart';
import 'pages/orders_page.dart';
import 'pages/payment_page.dart';
import 'pages/forgot_page.dart';
import 'pages/agreement_page.dart';
import 'pages/order_detail_page.dart';
import 'pages/order_form_page.dart';
import 'pages/materials_upload_page.dart';

void main() {
  runApp(const VisaIosApp());
}

class VisaIosApp extends StatelessWidget {
  const VisaIosApp({super.key});

  @override
  Widget build(BuildContext context) {
    // W9-1 screenshot hook: read `?page=` and `?lang=` from the URL so the
    // web build can deep-link to a specific page+locale for screenshot
    // capture. This is a debug-only override; native iOS uses MaterialApp
    // routing as before. URL params are ignored when absent.
    final params = Uri.base.queryParameters;
    final lang = params['lang'];
    final page = params['page'];
    final supportedLocales = AppLocalizations.supportedLocales;
    Locale? initialLocale;
    if (lang != null) {
      for (final l in supportedLocales) {
        if (l.languageCode == lang) { initialLocale = l; break; }
      }
    }
    String initialRoute = AppRoutes.home;
    if (page != null) {
      switch (page) {
        case 'home':       initialRoute = AppRoutes.home; break;
        case 'login':      initialRoute = AppRoutes.login; break;
        case 'register':   initialRoute = AppRoutes.register; break;
        case 'materials': initialRoute = AppRoutes.materials; break;
        case 'destinations': initialRoute = AppRoutes.destinations; break;
        case 'profile':   initialRoute = AppRoutes.profile; break;
        case 'orders':    initialRoute = AppRoutes.orders; break;
        case 'payment':   initialRoute = AppRoutes.payment; break;
        case 'forgot':    initialRoute = AppRoutes.forgot; break;
        case 'agreement': initialRoute = AppRoutes.agreement; break;
        case 'order-detail': initialRoute = AppRoutes.orderDetail; break;
        case 'order-form': initialRoute = AppRoutes.orderForm; break;
        case 'materials-upload': initialRoute = AppRoutes.materialsUpload; break;
      }
    }
    return MaterialApp(
      title: 'Visa Helper',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xFF1976D2),
          brightness: Brightness.light,
        ),
        useMaterial3: true,
      ),
      // 4 locales (en, zh, id, vi) — sourced from flutter_localizations +
      // generated AppLocalizations. The default locale is English; the device
      // locale is honored when it matches a supported language.
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      locale: initialLocale ?? const Locale('zh'),
      // Root route table — W8-1 uses name-based routing via onGenerateRoute.
      initialRoute: initialRoute,
      onGenerateRoute: AppRoutes.generateRoute,
    );
  }
}

class AppRoutes {
  static const String home = '/';
  static const String login = '/login';
  static const String register = '/register';
  static const String materials = '/materials';
  static const String destinations = '/destinations';
  static const String profile = '/profile';
  static const String orders = '/orders';
  static const String payment = '/payment';
  static const String forgot = '/forgot';
  static const String agreement = '/agreement';
  static const String orderDetail = '/order-detail';
  static const String orderForm = '/order-form';
  static const String materialsUpload = '/materials-upload';

  static Route<dynamic> generateRoute(RouteSettings settings) {
    switch (settings.name) {
      case home:      return MaterialPageRoute(builder: (_) => const HomePage());
      case login:     return MaterialPageRoute(builder: (_) => const LoginPage());
      case register: return MaterialPageRoute(builder: (_) => const RegisterPage());
      case materials: return MaterialPageRoute(builder: (_) => const MaterialsPage());
      case destinations: return MaterialPageRoute(builder: (_) => const DestinationsPage());
      case profile:    return MaterialPageRoute(builder: (_) => const ProfilePage());
      case orders:    return MaterialPageRoute(builder: (_) => const OrdersPage());
      case payment:   return MaterialPageRoute(builder: (_) => PaymentPage(orderNo: settings.arguments as String?));
      case forgot:    return MaterialPageRoute(builder: (_) => const ForgotPage());
      case agreement: return MaterialPageRoute(builder: (_) => const AgreementPage());
      case orderDetail: return MaterialPageRoute(builder: (_) => OrderDetailPage(orderNo: settings.arguments as String?));
      case orderForm: return MaterialPageRoute(builder: (_) => OrderFormPage(orderNo: settings.arguments as String?));
      case materialsUpload: return MaterialPageRoute(builder: (_) => MaterialsUploadPage(orderNo: settings.arguments as String?));
      default:        return MaterialPageRoute(builder: (_) => const HomePage());
    }
  }
}
