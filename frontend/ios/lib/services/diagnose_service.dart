// Diagnose service — visa eligibility quick-check (rule engine).
//
// POST /api/v2/diagnose  →  {score, level, factors[], suggestions[], policy_summary?}
// Public endpoint, no auth required (it's a pre-screening tool).

import 'dart:convert';
import 'package:http/http.dart' as http;

class DiagnoseFactor {
  final String name;
  final int impact; // -100..+100
  final String detail;
  final String category; // positive | negative | neutral

  const DiagnoseFactor({
    required this.name,
    required this.impact,
    required this.detail,
    required this.category,
  });

  factory DiagnoseFactor.fromJson(Map<String, dynamic> json) {
    return DiagnoseFactor(
      name: (json['name'] ?? '') as String,
      impact: (json['impact'] ?? 0) as int,
      detail: (json['detail'] ?? '') as String,
      category: (json['category'] ?? 'neutral') as String,
    );
  }
}

class DiagnoseResult {
  final String countryCode;
  final int score; // 0-100
  final String level; // high | medium | low
  final List<DiagnoseFactor> factors;
  final List<String> suggestions;
  final String? policySummary;

  const DiagnoseResult({
    required this.countryCode,
    required this.score,
    required this.level,
    required this.factors,
    required this.suggestions,
    this.policySummary,
  });

  factory DiagnoseResult.fromJson(Map<String, dynamic> json) {
    return DiagnoseResult(
      countryCode: (json['country_code'] ?? '') as String,
      score: (json['score'] ?? 0) as int,
      level: (json['level'] ?? 'medium') as String,
      factors: ((json['factors'] ?? []) as List)
          .map((e) => DiagnoseFactor.fromJson(e as Map<String, dynamic>))
          .toList(),
      suggestions: ((json['suggestions'] ?? []) as List).map((e) => e.toString()).toList(),
      policySummary: json['policy_summary'] as String?,
    );
  }
}

class DiagnoseException implements Exception {
  final String message;
  DiagnoseException(this.message);
  @override
  String toString() => 'DiagnoseException: $message';
}

class DiagnoseService {
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  final String baseUrl;
  final http.Client _client;

  DiagnoseService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  Future<DiagnoseResult> submit({
    required String countryCode,
    required String maritalStatus,
    required String incomeBucket,
    required String travelPurpose,
    required String travelHistory,
    required String visaHistory,
    required String employment,
    int? age,
    bool isSoloFemale = false,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/diagnose');
    final resp = await _client.post(
      url,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'country_code': countryCode,
        'marital_status': maritalStatus,
        'income_bucket': incomeBucket,
        'travel_purpose': travelPurpose,
        'travel_history': travelHistory,
        'visa_history': visaHistory,
        'employment': employment,
        if (age != null) 'age': age,
        'is_solo_female': isSoloFemale,
      }),
    );
    if (resp.statusCode != 200) {
      throw DiagnoseException('diagnose failed (${resp.statusCode})');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    if ((body['code'] ?? '1000') != '1000') {
      throw DiagnoseException((body['message'] ?? 'diagnose failed') as String);
    }
    final data = body['data'] as Map<String, dynamic>;
    return DiagnoseResult.fromJson(data);
  }
}