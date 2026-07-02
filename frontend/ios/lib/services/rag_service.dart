// RAG service — visa policy Q&A + per-country material checklist.
//
// POST /api/v2/rag/query  →  {answer, chunks[], followups[]}
// GET  /api/v2/rag/sources → list of seeded sources
// GET  /api/v2/rag/checklist?country_code=US → {materials[], fee, processing_time, validity}

import 'dart:convert';
import 'package:http/http.dart' as http;

class RAGChunk {
  final int chunkId;
  final String? sourceName;
  final String? sourceUrl;
  final double score;
  final String snippet;

  const RAGChunk({
    required this.chunkId,
    this.sourceName,
    this.sourceUrl,
    required this.score,
    required this.snippet,
  });

  factory RAGChunk.fromJson(Map<String, dynamic> json) {
    return RAGChunk(
      chunkId: (json['chunk_id'] ?? 0) as int,
      sourceName: json['source_name'] as String?,
      sourceUrl: json['source_url'] as String?,
      score: ((json['score'] ?? 0.0) as num).toDouble(),
      snippet: (json['snippet'] ?? '') as String,
    );
  }
}

class RAGAnswer {
  final String query;
  final String answer;
  final List<RAGChunk> chunks;
  final List<String> followups;

  const RAGAnswer({
    required this.query,
    required this.answer,
    required this.chunks,
    required this.followups,
  });

  factory RAGAnswer.fromJson(Map<String, dynamic> json) {
    return RAGAnswer(
      query: (json['query'] ?? '') as String,
      answer: (json['answer'] ?? '') as String,
      chunks: ((json['chunks'] ?? []) as List)
          .map((e) => RAGChunk.fromJson(e as Map<String, dynamic>))
          .toList(),
      followups: ((json['followups'] ?? []) as List).map((e) => e.toString()).toList(),
    );
  }
}

class ChecklistMaterial {
  final String name;
  final String? category; // base | financial | employment | travel | other
  final bool required;
  final String? note;

  const ChecklistMaterial({
    required this.name,
    this.category,
    required this.required,
    this.note,
  });

  factory ChecklistMaterial.fromJson(Map<String, dynamic> json) {
    return ChecklistMaterial(
      name: (json['name'] ?? json['title'] ?? '') as String,
      category: json['category'] as String?,
      required: (json['required'] ?? true) as bool,
      note: json['note'] as String?,
    );
  }
}

class Checklist {
  final String countryCode;
  final String? fee;
  final String? processingTime;
  final String? validity;
  final List<ChecklistMaterial> materials;

  const Checklist({
    required this.countryCode,
    this.fee,
    this.processingTime,
    this.validity,
    required this.materials,
  });

  factory Checklist.fromJson(Map<String, dynamic> json) {
    return Checklist(
      countryCode: (json['country_code'] ?? '') as String,
      fee: json['fee'] as String?,
      processingTime: json['processing_time'] as String?,
      validity: json['validity'] as String?,
      materials: ((json['materials'] ?? []) as List)
          .map((e) => ChecklistMaterial.fromJson(e as Map<String, dynamic>))
          .toList(),
    );
  }
}

class RAGException implements Exception {
  final String message;
  RAGException(this.message);
  @override
  String toString() => 'RAGException: $message';
}

class RAGService {
  static const String defaultBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8000',
  );

  final String baseUrl;
  final http.Client _client;

  RAGService({String? baseUrl, http.Client? client})
      : baseUrl = baseUrl ?? defaultBaseUrl,
        _client = client ?? http.Client();

  Future<RAGAnswer> query({
    required String query,
    String? countryCode,
    int topK = 3,
    required String accessToken,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/rag/query');
    final resp = await _client.post(
      url,
      headers: {
        'Content-Type': 'application/json',
        'Authorization': 'Bearer $accessToken',
      },
      body: jsonEncode({
        'query': query,
        if (countryCode != null) 'country_code': countryCode,
        'top_k': topK,
      }),
    );
    if (resp.statusCode != 200) {
      throw RAGException('rag query failed (${resp.statusCode})');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    if ((body['code'] ?? '1000') != '1000') {
      throw RAGException((body['message'] ?? 'rag query failed') as String);
    }
    return RAGAnswer.fromJson(body['data'] as Map<String, dynamic>);
  }

  Future<Checklist> checklist({
    required String countryCode,
    required String accessToken,
  }) async {
    final url = Uri.parse('$baseUrl/api/v2/rag/checklist').replace(
      queryParameters: {'country_code': countryCode},
    );
    final resp = await _client.get(
      url,
      headers: {'Authorization': 'Bearer $accessToken'},
    );
    if (resp.statusCode != 200) {
      throw RAGException('checklist failed (${resp.statusCode})');
    }
    final body = jsonDecode(resp.body) as Map<String, dynamic>;
    if ((body['code'] ?? '1000') != '1000') {
      throw RAGException((body['message'] ?? 'checklist failed') as String);
    }
    return Checklist.fromJson((body['data'] ?? {}) as Map<String, dynamic>);
  }
}