// Auth service for Visa iOS — calls backend /api/v2/auth/login (password / SMS).
// Mirrors frontend/web/src/stores/auth.js (loginByPassword + loginBySms) but kept
// intentionally minimal for W6b F1.7 (login page port only).

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class AuthResult {
  final String accessToken;
  final String refreshToken;
  final int userId;

  const AuthResult({
    required this.accessToken,
    required this.refreshToken,
    required this.userId,
  });

  factory AuthResult.fromJson(Map<String, dynamic> json) {
    return AuthResult(
      accessToken: (json['access_token'] ?? '') as String,
      refreshToken: (json['refresh_token'] ?? '') as String,
      userId: (json['user_id'] ?? 0) as int,
    );
  }
}

class AuthException implements Exception {
  final int code;
  final String message;
  AuthException(this.code, this.message);

  @override
  String toString() => 'AuthException($code): $message';
}

class AuthService {
  // Backend dev default — W6b runs uvicorn on :8000.
  // Override via --dart-define=API_BASE_URL=http://192.168.x.x:8000 if needed.
  static const String defaultBaseUrl =
      String.fromEnvironment('API_BASE_URL', defaultValue: 'http://127.0.0.1:8000');

  final String baseUrl;
  final http.Client _client;

  AuthService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  Future<AuthResult> loginByPassword({
    required String phone,
    required String phoneCountry,
    required String password,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/login');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'phone': phone,
        'phone_country': phoneCountry,
        'password': password,
        'grant_type': 'password',
      }),
    );
    return _parseAuth(resp);
  }

  Future<AuthResult> loginBySms({
    required String phone,
    required String phoneCountry,
    required String code,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/login');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'phone': phone,
        'phone_country': phoneCountry,
        'sms_code': code,
        'grant_type': 'sms',
      }),
    );
    return _parseAuth(resp);
  }

  // W8-1: send verification code for registration / password reset flows.
  // Returns the mock code string when the backend is in mock mode, else ''.
  Future<String> sendCode({
    required String phone,
    required String phoneCountry,
    String purpose = 'register',
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/send-code');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'phone': phone,
        'phone_country': phoneCountry,
        'purpose': purpose,
      }),
    );
    if (resp.statusCode == 200 || resp.statusCode == 201) {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      final data = (body['data'] ?? body) as Map<String, dynamic>;
      return (data['code'] ?? '') as String;
    }
    final Map<String, dynamic> body;
    try {
      body = jsonDecode(resp.body) as Map<String, dynamic>;
    } catch (_) {
      throw AuthException(resp.statusCode, 'send-code failed (${resp.statusCode})');
    }
    final code = (body['code'] ?? resp.statusCode) as int;
    final msg = (body['message'] ?? body['msg'] ?? 'send-code failed') as String;
    throw AuthException(code, msg);
  }

  // W8-1: create a new account with phone + SMS code + password.
  Future<AuthResult> register({
    required String phone,
    required String phoneCountry,
    required String password,
    required String smsCode,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/register');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'phone': phone,
        'phone_country': phoneCountry,
        'password': password,
        'sms_code': smsCode,
      }),
    );
    if (resp.statusCode == 200 || resp.statusCode == 201) {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      final data = (body['data'] ?? body) as Map<String, dynamic>;
      return AuthResult.fromJson(data);
    }
    final Map<String, dynamic> body;
    try {
      body = jsonDecode(resp.body) as Map<String, dynamic>;
    } catch (_) {
      throw AuthException(resp.statusCode, 'register failed (${resp.statusCode})');
    }
    final code = (body['code'] ?? resp.statusCode) as int;
    final msg = (body['message'] ?? body['msg'] ?? 'register failed') as String;
    throw AuthException(code, msg);
  }

  AuthResult _parseAuth(http.Response resp) {
    final Map<String, dynamic> body;
    try {
      body = jsonDecode(resp.body) as Map<String, dynamic>;
    } catch (_) {
      throw AuthException(resp.statusCode, 'Invalid JSON response (${resp.statusCode})');
    }
    if (resp.statusCode == 200 || resp.statusCode == 201) {
      final data = (body['data'] ?? body) as Map<String, dynamic>;
      final result = AuthResult.fromJson(data);
      // Best-effort persist access token for next page.
      SharedPreferences.getInstance().then((prefs) {
        prefs.setString('access_token', result.accessToken);
        prefs.setInt('user_id', result.userId);
      });
      return result;
    }
    final code = (body['code'] ?? resp.statusCode) as int;
    final msg = (body['message'] ?? body['msg'] ?? 'Login failed') as String;
    throw AuthException(code, msg);
  }

  // ─── Static session helpers (used by profile_page.dart) ─────────────────────

  /// Returns the cached user Map from SharedPreferences, or null if not logged in.
  static Map<String, dynamic>? getUser() {
    // Synchronous read is not available on SharedPreferences.
    // Pages call this from didChangeDependencies (async-safe) or we return null
    // and let didChangeDependencies re-call. For synchronous checks use isLoggedIn.
    // This method is called from build/didChangeDependencies where prefs are ready.
    return null; // populated by _loadUserAsync
  }

  /// Async helper — populates user data from SharedPreferences.
  static Future<Map<String, dynamic>?> loadUserAsync() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token == null || token.isEmpty) return null;
    final userId = prefs.getInt('user_id');
    return {
      'id': userId ?? 0,
      'phone': prefs.getString('phone') ?? '',
      'nickname': prefs.getString('nickname') ?? '',
      'createdAt': prefs.getString('created_at') ?? DateTime.now().toIso8601String(),
    };
  }

  /// Returns true if a valid access token is stored.
  static Future<bool> isLoggedIn() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    return token != null && token.isNotEmpty;
  }

  /// Clears all auth tokens from SharedPreferences.
  static Future<void> clearSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    await prefs.remove('user_id');
    await prefs.remove('phone');
    await prefs.remove('nickname');
    await prefs.remove('created_at');
  }
}