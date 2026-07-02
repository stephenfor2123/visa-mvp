// ResourcesPage — RAG-backed visa policy Q&A.
//
// Layout:
//   - Search bar (query)
//   - Country filter (optional)
//   - Result: answer text + chunk sources + follow-up question chips

import 'package:flutter/material.dart';
import '../services/auth_service.dart';
import '../services/rag_service.dart';

class ResourcesPage extends StatefulWidget {
  const ResourcesPage({super.key});

  @override
  State<ResourcesPage> createState() => _ResourcesPageState();
}

class _ResourcesPageState extends State<ResourcesPage> {
  final _queryCtrl = TextEditingController();
  String? _countryCode;
  bool _loading = false;
  String? _error;
  RAGAnswer? _answer;

  final _ragSvc = RAGService();

  Future<void> _ask() async {
    final q = _queryCtrl.text.trim();
    if (q.isEmpty) return;
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final token = await AuthService.getAccessToken();
      if (token == null) throw '请先登录';
      final ans = await _ragSvc.query(query: q, countryCode: _countryCode, accessToken: token);
      setState(() => _answer = ans);
    } catch (e) {
      setState(() => _error = e.toString());
    } finally {
      if (mounted) setState(() => _loading = false);
    }
  }

  void _askFollowup(String q) {
    _queryCtrl.text = q;
    _ask();
  }

  @override
  void dispose() {
    _queryCtrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(icon: const Icon(Icons.arrow_back), onPressed: () => Navigator.of(context).maybePop()),
        title: const Text('签证政策问答', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
      ),
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Text('问任何签证相关问题', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
              const SizedBox(height: 4),
              const Text('AI 会从 4 国官方资料里找答案。', style: TextStyle(fontSize: 13, color: Color(0xFF64748B))),
              const SizedBox(height: 16),
              TextField(
                controller: _queryCtrl,
                decoration: InputDecoration(
                  hintText: '例如：美国签证费用是多少',
                  border: const OutlineInputBorder(),
                  suffixIcon: IconButton(icon: const Icon(Icons.send, color: Color(0xFF3B6EF5)), onPressed: _ask),
                ),
                onSubmitted: (_) => _ask(),
              ),
              const SizedBox(height: 12),
              SizedBox(
                height: 36,
                child: ListView(
                  scrollDirection: Axis.horizontal,
                  children: [
                    _filterChip(null, '全部'),
                    ...['US', 'GB', 'AU', 'SCHENGEN'].map((cc) => _filterChip(cc, _flagOf(cc))),
                  ],
                ),
              ),
              const SizedBox(height: 12),
              Expanded(child: _buildBody()),
            ],
          ),
        ),
      ),
    );
  }

  Widget _filterChip(String? cc, String label) {
    final selected = _countryCode == cc;
    return Padding(
      padding: const EdgeInsets.only(right: 8),
      child: FilterChip(
        label: Text(label, style: TextStyle(fontSize: 12, color: selected ? Colors.white : const Color(0xFF475569))),
        selected: selected,
        onSelected: (_) => setState(() => _countryCode = cc),
        backgroundColor: Colors.white,
        selectedColor: const Color(0xFF3B6EF5),
        checkmarkColor: Colors.white,
        side: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
    );
  }

  Widget _buildBody() {
    if (_loading) return const Center(child: CircularProgressIndicator());
    if (_error != null) {
      return Center(
        child: Column(mainAxisAlignment: MainAxisAlignment.center, children: [
          const Icon(Icons.error_outline, size: 48, color: Color(0xFF94A3B8)),
          const SizedBox(height: 12),
          Text(_error!, textAlign: TextAlign.center, style: const TextStyle(color: Color(0xFF64748B))),
          const SizedBox(height: 16),
          ElevatedButton(onPressed: _ask, child: const Text('重试')),
        ]),
      );
    }
    if (_answer == null) {
      return const Center(child: Text('开始提问吧', style: TextStyle(color: Color(0xFF94A3B8))));
    }
    final a = _answer!;
    return ListView(children: [
      Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(12), border: Border.all(color: const Color(0xFFE2E8F0))),
        child: Text(a.answer, style: const TextStyle(fontSize: 14, color: Color(0xFF0F172A), height: 1.6)),
      ),
      if (a.followups.isNotEmpty) ...[
        const SizedBox(height: 16),
        const Text('追问', style: TextStyle(fontSize: 13, color: Color(0xFF64748B), fontWeight: FontWeight.w500)),
        const SizedBox(height: 8),
        Wrap(spacing: 8, runSpacing: 8, children: a.followups.map((q) => ActionChip(
          label: Text(q, style: const TextStyle(fontSize: 12)),
          onPressed: () => _askFollowup(q),
        )).toList()),
      ],
      if (a.chunks.isNotEmpty) ...[
        const SizedBox(height: 16),
        const Text('来源', style: TextStyle(fontSize: 13, color: Color(0xFF64748B), fontWeight: FontWeight.w500)),
        const SizedBox(height: 8),
        ...a.chunks.map((c) => Container(
          margin: const EdgeInsets.only(bottom: 8),
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(color: const Color(0xFFF8FAFC), borderRadius: BorderRadius.circular(8)),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            if (c.sourceName != null) Text(c.sourceName!, style: const TextStyle(fontSize: 12, color: Color(0xFF3B6EF5), fontWeight: FontWeight.w600)),
            const SizedBox(height: 4),
            Text(c.snippet, maxLines: 3, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
            const SizedBox(height: 4),
            Text('相关度: ${(c.score * 100).toStringAsFixed(1)}%', style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8))),
          ]),
        )),
      ],
    ]);
  }

  String _flagOf(String cc) {
    const flags = {'US': '🇺🇸', 'GB': '🇬🇧', 'AU': '🇦🇺', 'SCHENGEN': '🇪🇺'};
    return flags[cc] ?? cc;
  }
}