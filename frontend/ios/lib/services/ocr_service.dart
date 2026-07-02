// OCR service — passport recognition + field extraction.
// Mirrors frontend/web/src/api/auth.js + the /api/v2/ocr/recognize endpoint.
//
// POST /api/v2/ocr/recognize  (multipart: file + lang)  →  {items[], fields{}, preprocessed, warnings[]}

import 'dart:convert';
import 'dart:io';
import 'package:http/http.dart' as http;

class OCRItem {
  final String text;
  final List<List<double>> bbox;
  final double confidence;

  const OCRItem({required this.text, required this.bbox, required this.confidence});

  factory OCRItem.fromJson(Map<String, dynamic> json) {
    return OCRItem(
      text: (json['text'] ?? '') as String,
      bbox: ((json['bbox'] ?? []) as List)
          .map((p) => ((p ?? []) as List).map((c) => (c as num).toDouble()).toList())
          .toList(),
      confidence: ((json['confidence'] ?? 0.0) as num).toDouble(),
    );
  }
}

class PassportFields {
  final String? passportNo;
  final String? surname;
  final String? givenName;
  final String? sex;
  final String? nationality;
  final String? dob;
  final String? expiry;
  final String? countryCode;
  final bool isPassportDoc;
  final String? rawText;

  const PassportFields({
    this.passportNo,
    this.surname,
    this.givenName,
    this.sex,
    this.nationality,
    this.dob,
    this.expiry,
    this.countryCode,
    required this.isPassportDoc,
    this.rawText,
  });

  factory PassportFields.fromJson(Map<String, dynamic> json) {
    return PassportFields(
      passportNo: json['passport_no'] as String?,
      surname: json['surname'] as String?,
      givenName: json['given_name'] as String?,
      sex: json['sex'] as String?,
      nationality: json['nationality'] as String?,
      dob: json['dob'] as String?,
      expiry: json['expiry'] as String?,
      countryCode: json['country_code'] as String?,
      isPassportDoc: (json['is_passport_doc'] ?? false) as bool,
      rawText: json['raw_text'] as String?,
    );
  }

  bool get isComplete =>
      (passportNo != null && passportNo!.isNotEmpty) &&
      (surname != null && surname!.isNotEmpty);
}

class OCRResult {
  final List<OCRItem> items;
  final PassportFields fields;
  final String lang;
  final bool preprocessed;
  final List<String> warnings;

  const OCRResult({
    required this.items,
    required this.fields,
    required this.lang,
    required this.preprocessed,
    required this.warnings,
  });

  factory OCRResult.fromJson(Map<String, dynamic> json) {
    return OCRResult(
      items: ((json['items'] ?? []) as List)
          .map((e) => OCRItem.fromJson(e as Map<String, dynamic>))
          .toList(),
      fields: PassportFields.fromJson((json['fields'] ?? {}) as Map<String, dynamic>),
      lang: (json['lang'] ?? 'en') as String,
      preprocessed: (json['preprocessed'] ?? false) as bool,
      warnings: ((json['preprocess_warnings'] ?? []) as List).map((e) => e.toString()).toList(),
    );
  }
}

class OCRException implements Exception {
  final String message;
  OCRException(this.message);
  @override
  String toString() => 'OCRException: $message';
}

class OCRService {
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  final String baseUrl;
  final http.Client _client;

  OCRService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  Future<OCRResult> recognize({
    required File file,
    String lang = 'en',
    required String accessToken,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/ocr/recognize');
    final req = http.MultipartRequest('POST', url)
      ..headers['Authorization'] = 'Bearer $accessToken'
      ..fields['lang'] = lang
      ..files.add(await http.MultipartFile.fromPath('file', file.path));
    final streamed = await _client.send(req);
    final resp = await http.Response.fromStream(streamed);
    if (resp.statusCode != 200) {
      throw OCRException('ocr failed (${resp.statusCode})');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    if ((body['code'] ?? '1000') != '1000') {
      throw OCRException((body['message'] ?? 'ocr failed') as String);
    }
    return OCRResult.fromJson(body['data'] as Map<String, dynamic>);
  }
}