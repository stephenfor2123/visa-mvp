// Apply service — create order + upload materials + submit for processing.
// Wraps /api/v2/orders + /api/v2/materials endpoints.

import 'dart:convert';
import 'package:http/http.dart' as http;

class OrderDraft {
  final String countryCode;
  final String visaType; // tourism | business | student | family
  final String? travelDateFrom; // ISO YYYY-MM-DD
  final String? travelDateTo;
  final String? departureCity;
  final String? emergencyContact;
  final String? purposeOfTrip;

  const OrderDraft({
    required this.countryCode,
    required this.visaType,
    this.travelDateFrom,
    this.travelDateTo,
    this.departureCity,
    this.emergencyContact,
    this.purposeOfTrip,
  });

  Map<String, dynamic> toJson() => {
        'country_code': countryCode,
        'visa_type': visaType,
        if (travelDateFrom != null) 'travel_date_from': travelDateFrom,
        if (travelDateTo != null) 'travel_date_to': travelDateTo,
        if (departureCity != null) 'departure_city': departureCity,
        if (emergencyContact != null) 'emergency_contact': emergencyContact,
        if (purposeOfTrip != null) 'purpose_of_trip': purposeOfTrip,
      };
}

class OrderCreated {
  final String orderNo;
  final String countryCode;
  final String status; // draft | submitted | paid | processing | approved | rejected
  final String? createdAt;

  const OrderCreated({
    required this.orderNo,
    required this.countryCode,
    required this.status,
    this.createdAt,
  });

  factory OrderCreated.fromJson(Map<String, dynamic> json) {
    return OrderCreated(
      orderNo: (json['order_no'] ?? '') as String,
      countryCode: (json['country_code'] ?? '') as String,
      status: (json['status'] ?? 'draft') as String,
      createdAt: json['created_at'] as String?,
    );
  }
}

class ApplyException implements Exception {
  final String message;
  ApplyException(this.message);
  @override
  String toString() => 'ApplyException: $message';
}

class ApplyService {
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  final String baseUrl;
  final http.Client _client;

  ApplyService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  Future<OrderCreated> createOrder({
    required OrderDraft draft,
    required String accessToken,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/orders');
    final resp = await _client.post(
      url,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      },
      body: jsonEncode(draft.toJson()),
    );
    if (resp.statusCode != 200 && resp.statusCode != 201) {
      throw ApplyException('create order failed (${resp.statusCode})');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    if ((body['code'] ?? '1000') != '1000') {
      throw ApplyException((body['message'] ?? 'create order failed') as String);
    }
    return OrderCreated.fromJson((body['data'] ?? {}) as Map<String, dynamic>);
  }
}