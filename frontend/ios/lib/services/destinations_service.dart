// Destinations service — fetches 29 supported countries from backend.
// Mirrors frontend/web/src/api/destinations.js.
//
// Routing:
//   - GET /api/v2/destinations?lang=&visa_type=  → 29 country list (US/AU/GB/SCHENGEN hero + 26 schengen members)
//   - W32 schema adds: visa_fee_usd, valid_days, process_days on each row

import 'dart:convert';
import 'package:http/http.dart' as http;

class Destination {
  final int id;
  final String countryCode;
  final String countryName;
  final String? subtitle;
  final String? coverImage;
  final List<String> visaTypes;
  final bool enabled;
  final int? visaFeeUsd;     // cents (USD), W32 Atlys-style fee chip
  final int? validDays;      // W32: e.g. 730 = 2 years
  final int? processDays;    // W32: typical processing days

  const Destination({
    required this.id,
    required this.countryCode,
    required this.countryName,
    this.subtitle,
    this.coverImage,
    required this.visaTypes,
    required this.enabled,
    this.visaFeeUsd,
    this.validDays,
    this.processDays,
  });

  factory Destination.fromJson(Map<String, dynamic> json) {
    return Destination(
      id: (json['id'] ?? 0) as int,
      countryCode: (json['country_code'] ?? '') as String,
      countryName: (json['country_name'] ?? '') as String,
      subtitle: json['subtitle'] as String?,
      coverImage: json['cover_image'] as String?,
      visaTypes: ((json['visa_types'] ?? []) as List).map((e) => e.toString()).toList(),
      enabled: (json['enabled'] ?? false) as bool,
      visaFeeUsd: json['visa_fee_usd'] as int?,
      validDays: json['valid_days'] as int?,
      processDays: json['process_days'] as int?,
    );
  }

  // Display helpers
  String get feeLabel {
    if (visaFeeUsd == null) return '';
    final dollars = visaFeeUsd! ~/ 100;
    return '\$$dollars';
  }

  String get validityLabel {
    if (validDays == null) return '';
    if (validDays! >= 365) {
      final years = (validDays! / 365).round();
      return years == 1 ? '1 YEAR' : '$years YEARS';
    }
    final months = (validDays! / 30).round();
    return months == 1 ? '1 MONTH' : '$months MONTHS';
  }

  String get processLabel {
    if (processDays == null) return '';
    return '$processDays DAYS';
  }
}

class DestinationsException implements Exception {
  final String message;
  DestinationsException(this.message);
  @override
  String toString() => 'DestinationsException: $message';
}

class DestinationsService {
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  final String baseUrl;
  final http.Client _client;

  DestinationsService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  /// List destinations; localized via the `lang` query param.
  Future<List<Destination>> list({String lang = 'zh-CN', String? visaType}) async {
    final qp = <String, String>{'lang': lang};
    if (visaType != null) qp['visa_type'] = visaType;
    final url = Uri.parse('$baseUrl/api/v2/destinations').replace(queryParameters: qp);
    final resp = await _client.get(url);
    if (resp.statusCode != 200) {
      throw DestinationsException('destinations fetch failed (${resp.statusCode})');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    final data = body['data'];
    final items = data is List
        ? data
        : (data is Map ? (data['items'] ?? data['list'] ?? []) as List : <dynamic>[]);
    return items
        .map((e) => Destination.fromJson(e as Map<String, dynamic>))
        .toList();
  }

  /// Visa-system grouping — hero 4 (US/AU/GB/SCHENGEN) on top, schengen 26 below.
  /// Mirrors web's groupCountriesByVisaType.
  Map<String, List<Destination>> groupByVisaType(List<Destination> all) {
    const hero = {'US', 'AU', 'GB', 'SCHENGEN'};
    final national = <Destination>[];
    final schengen = <Destination>[];
    for (final d in all) {
      if (hero.contains(d.countryCode)) {
        national.add(d);
      } else {
        schengen.add(d);
      }
    }
    return {'national': national, 'schengen': schengen};
  }

  /// Static fallback used when API is offline (matches web's FALLBACK_DESTINATIONS).
  static List<Destination> fallback({String lang = 'zh-CN'}) {
    final rows = <Map<String, dynamic>>[
      {'code': 'US', 'name_zh': '美国', 'name_en': 'United States', 'name_id': 'Amerika Serikat', 'name_vi': 'Hoa Kỳ', 'fee': 18500, 'valid': 365, 'proc': 5},
      {'code': 'AU', 'name_zh': '澳大利亚', 'name_en': 'Australia', 'name_id': 'Australia', 'name_vi': 'Úc', 'fee': 14500, 'valid': 365, 'proc': 4},
      {'code': 'GB', 'name_zh': '英国', 'name_en': 'United Kingdom', 'name_id': 'Inggris', 'name_vi': 'Anh', 'fee': 12500, 'valid': 180, 'proc': 3},
      {'code': 'SCHENGEN', 'name_zh': '申根', 'name_en': 'Schengen', 'name_id': 'Schengen', 'name_vi': 'Schengen', 'fee': 9000, 'valid': 180, 'proc': 7},
    ];
    String pickName(Map<String, dynamic> r) {
      if (lang.startsWith('en')) return r['name_en'] as String;
      if (lang.startsWith('id')) return r['name_id'] as String;
      if (lang.startsWith('vi')) return r['name_vi'] as String;
      return r['name_zh'] as String;
    }
    return [
      for (var i = 0; i < rows.length; i++)
        Destination(
          id: i + 1,
          countryCode: rows[i]['code'] as String,
          countryName: pickName(rows[i]),
          visaTypes: const ['tourism', 'business'],
          enabled: rows[i]['code'] == 'US', // only US live in MVP
          visaFeeUsd: rows[i]['fee'] as int?,
          validDays: rows[i]['valid'] as int?,
          processDays: rows[i]['proc'] as int?,
        ),
    ];
  }
}