// Auth service for Visa iOS — W32 schema (email/username + password).
//
// Mirrors frontend/web/src/api/auth.js — supports W32's dual-identifier
// (email OR username) login + register with username field.
//
// Routing:
//   - POST /api/v2/auth/register  → {username, email, password, nickname?, language_pref?}
//   - POST /api/v2/auth/login     → {account, password}  (account = email | username)
//   - POST /api/v2/auth/refresh   → {refresh_token}
//   - POST /api/v2/auth/reset-password → {account, new_password, sms_code?}
//   - POST /api/v2/auth/send-code → {phone, phone_country, purpose}  (legacy)

import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

class AuthUser {
  final int id;
  final String uuid;
  final String username;
  final String email;
  final String phone;
  final String phoneCountry;
  final String nickname;
  final String? avatarUrl;
  final String languagePref;
  final String status;
  final String createdAt;

  const AuthUser({
    required this.id,
    required this.uuid,
    required this.username,
    required this.email,
    required this.phone,
    required this.phoneCountry,
    required this.nickname,
    required this.avatarUrl,
    required this.languagePref,
    required this.status,
    required this.createdAt,
  });

  factory AuthUser.fromJson(Map<String, dynamic> json) {
    return AuthUser(
      id: (json['id'] ?? 0) as int,
      uuid: (json['uuid'] ?? '') as String,
      username: (json['username'] ?? '') as String,
      email: (json['email'] ?? '') as String,
      phone: (json['phone'] ?? '') as String,
      phoneCountry: (json['phone_country'] ?? '+86') as String,
      nickname: (json['nickname'] ?? '') as String,
      avatarUrl: json['avatar_url'] as String?,
      languagePref: (json['language_pref'] ?? 'zh-CN') as String,
      status: (json['status'] ?? 'active') as String,
      createdAt: (json['created_at'] ?? '') as String,
    );
  }

  /// Dict-style access for legacy callers (`user['field']`).
  /// Supported keys: id, uuid, username, email, phone, phone_country, nickname,
  /// avatar_url, language_pref, status, created_at.
  dynamic operator [](String key) {
    switch (key) {
      case 'id': return id;
      case 'uuid': return uuid;
      case 'username': return username;
      case 'email': return email;
      case 'phone': return phone;
      case 'phone_country': return phoneCountry;
      case 'nickname': return nickname;
      case 'avatar_url': return avatarUrl;
      case 'language_pref': return languagePref;
      case 'status': return status;
      case 'created_at': return createdAt;
      default: return null;
    }
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'uuid': uuid,
        'username': username,
        'email': email,
        'phone': phone,
        'phone_country': phoneCountry,
        'nickname': nickname,
        'avatar_url': avatarUrl,
        'language_pref': languagePref,
        'status': status,
        'created_at': createdAt,
      };
}

class AuthResult {
  final String accessToken;
  final String refreshToken;
  final String tokenType;
  final int expiresIn;
  final AuthUser user;

  const AuthResult({
    required this.accessToken,
    required this.refreshToken,
    required this.tokenType,
    required this.expiresIn,
    required this.user,
  });

  factory AuthResult.fromJson(Map<String, dynamic> json) {
    return AuthResult(
      accessToken: (json['access_token'] ?? '') as String,
      refreshToken: (json['refresh_token'] ?? '') as String,
      tokenType: (json['token_type'] ?? 'Bearer') as String,
      expiresIn: (json['expires_in'] ?? 7200) as int,
      user: AuthUser.fromJson((json['user'] ?? {}) as Map<String, dynamic>),
    );
  }
}

class AuthException implements Exception {
  final int httpStatus;
  final int apiCode;
  final String message;

  AuthException(this.httpStatus, this.apiCode, this.message);

  @override
  String toString() => 'AuthException(http=$httpStatus, code=$apiCode): $message';
}

class AuthService {
  // Backend dev default — uvicorn on :8000.
  // Override via --dart-define=API_BASE_URL=http://192.168.x.x:8000 if needed.
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  final String baseUrl;
  final http.Client _client;

  AuthService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  // ─── Register (W32 schema: username + email + password) ──────────────────────

  Future<AuthResult> register({
    required String username,
    required String email,
    required String password,
    String? nickname,
    String languagePref = 'zh-CN',
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/register');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'username': username,
        'email': email,
        'password': password,
        if (nickname != null && nickname.isNotEmpty) 'nickname': nickname,
        'language_pref': languagePref,
      }),
    );
    return await _parseAuth(resp);
  }

  // ─── Login by account (email OR username) ───────────────────────────────────

  Future<AuthResult> loginByAccount({
    required String account,
    required String password,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/login');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'account': account,
        'password': password,
      }),
    );
    return await _parseAuth(resp);
  }

  // ─── Login (legacy phone + SMS) — kept for backward compatibility ────────────

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
    return await _parseAuth(resp);
  }

  // ─── SMS code (legacy) ──────────────────────────────────────────────────────

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
    throw _parseError(resp, 'send-code failed');
  }

  // ─── Google Sign-In ──────────────────────────────────────────────────────────

  Future<AuthResult> loginWithGoogle(String idToken) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/google');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'id_token': idToken}),
    );
    return await _parseAuth(resp);
  }

  // ─── Refresh ─────────────────────────────────────────────────────────────────

  Future<AuthResult?> refresh() async {
    final prefs = await SharedPreferences.getInstance();
    final rt = prefs.getString('refresh_token');
    if (rt == null || rt.isEmpty) return null;
    final url = Uri.parse('$baseUrl/api/v2/auth/refresh');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'refresh_token': rt}),
    );
    if (resp.statusCode == 200 || resp.statusCode == 201) {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      final data = (body['data'] ?? body) as Map<String, dynamic>;
      final result = AuthResult.fromJson(data);
      await prefs.setString('access_token', result.accessToken);
      await prefs.setString('refresh_token', result.refreshToken);
      return result;
    }
    return null;
  }

  // ─── Reset password (W32: by account, no SMS) ───────────────────────────────

  Future<void> resetPassword({
    required String account,
    required String newPassword,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/auth/reset-password');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'account': account,
        'new_password': newPassword,
      }),
    );
    if (resp.statusCode != 200 && resp.statusCode != 201) {
      throw _parseError(resp, 'reset-password failed');
    }
  }

  // ─── Internal helpers ───────────────────────────────────────────────────────

  Future<AuthResult> _parseAuth(http.Response resp) async {
    final Map<String, dynamic> body;
    try {
      body = jsonDecode(resp.body) as Map<String, dynamic>;
    } catch (_) {
      throw AuthException(resp.statusCode, 0, 'Invalid JSON response (${resp.statusCode})');
    }
    if (resp.statusCode == 200 || resp.statusCode == 201) {
      if ((body['code'] ?? '1000') != '1000' && body['data'] == null) {
        throw AuthException(resp.statusCode, _asInt(body['code']), (body['message'] ?? 'login failed') as String);
      }
      final data = (body['data'] ?? body) as Map<String, dynamic>;
      final result = AuthResult.fromJson(data);
      final prefs = await SharedPreferences.getInstance();
      await prefs.setString('access_token', result.accessToken);
      await prefs.setString('refresh_token', result.refreshToken);
      await prefs.setInt('user_id', result.user.id);
      await prefs.setString('username', result.user.username);
      await prefs.setString('email', result.user.email);
      await prefs.setString('nickname', result.user.nickname);
      await prefs.setString('language_pref', result.user.languagePref);
      return result;
    }
    throw _parseError(resp, 'auth failed');
  }

  AuthException _parseError(http.Response resp, String fallback) {
    try {
      final body = jsonDecode(resp.body) as Map<String, dynamic>;
      return AuthException(
        resp.statusCode,
        _asInt(body['code']),
        (body['message'] ?? body['msg'] ?? fallback) as String,
      );
    } catch (_) {
      return AuthException(resp.statusCode, resp.statusCode, '$fallback (${resp.statusCode})');
    }
  }

  int _asInt(dynamic v) {
    if (v is int) return v;
    if (v is String) return int.tryParse(v) ?? 0;
    return 0;
  }

  // ─── Static session helpers ──────────────────────────────────────────────────

  static Future<AuthUser?> loadUserAsync() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    if (token == null || token.isEmpty) return null;
    return AuthUser(
      id: prefs.getInt('user_id') ?? 0,
      uuid: '',
      username: prefs.getString('username') ?? '',
      email: prefs.getString('email') ?? '',
      phone: '',
      phoneCountry: '+86',
      nickname: prefs.getString('nickname') ?? '',
      avatarUrl: null,
      languagePref: prefs.getString('language_pref') ?? 'zh-CN',
      status: 'active',
      createdAt: '',
    );
  }

  static Future<String?> getAccessToken() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('access_token');
    return (token != null && token.isNotEmpty) ? token : null;
  }

  static Future<bool> isLoggedIn() async {
    final token = await getAccessToken();
    return token != null;
  }

  static Future<void> clearSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('access_token');
    await prefs.remove('refresh_token');
    await prefs.remove('user_id');
    await prefs.remove('username');
    await prefs.remove('email');
    await prefs.remove('nickname');
    await prefs.remove('language_pref');
  }
}