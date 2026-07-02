// Destinations page — W32 port: hero 5 国封面 + 26 国 schengen grid.
//
// Sections:
//   - Search bar → CountrySearchModal
//   - Hero 5 国 (US / AU / GB / Schengen / JP) 大图卡片
//   - Schengen 26 国 grid (展开/收起)

import 'package:flutter/material.dart';
import '../services/destinations_service.dart';
import '../widgets/country_search_modal.dart';
import 'apply_page.dart';

class DestinationsPage extends StatefulWidget {
  const DestinationsPage({super.key});

  @override
  State<DestinationsPage> createState() => _DestinationsPageState();
}

class _DestinationsPageState extends State<DestinationsPage> {
  List<Destination> _all = const [];
  List<Destination> _hero = const [];
  List<Destination> _schengen = const [];
  bool _schengenExpanded = false;
  bool _loading = true;

  final _destSvc = DestinationsService();

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    try {
      final list = await _destSvc.list(lang: 'zh-CN');
      final hero = list.where((d) => const {'US', 'AU', 'GB', 'SCHENGEN', 'JP'}.contains(d.countryCode)).toList();
      final schengen = list.where((d) => !const {'US', 'AU', 'GB', 'JP'}.contains(d.countryCode)).toList();
      setState(() {
        _all = list;
        _hero = hero.isEmpty ? DestinationsService.fallback() : hero;
        _schengen = schengen;
        _loading = false;
      });
    } catch (_) {
      setState(() {
        _all = DestinationsService.fallback();
        _hero = DestinationsService.fallback();
        _schengen = const [];
        _loading = false;
      });
    }
  }

  void _openApply(Destination d) {
    Navigator.of(context).push(MaterialPageRoute(builder: (_) => ApplyPage(initialCountryCode: d.countryCode)));
  }

  void _openSearch() {
    CountrySearchModal.show(context, countries: _all, onSelect: _openApply);
  }

  @override
  Widget build(BuildContext context) {
    if (_loading) return const Scaffold(body: Center(child: CircularProgressIndicator()));
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: const Text('选择目的地', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
        actions: [
          IconButton(icon: const Icon(Icons.search), onPressed: _openSearch),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Hero 5 国封面
          ..._hero.map((d) => _heroCoverCard(d)),
          const SizedBox(height: 24),
          // Schengen 26 国
          if (_schengen.isNotEmpty) ...[
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Row(children: [
                  const Text('🇪🇺', style: TextStyle(fontSize: 18)),
                  const SizedBox(width: 6),
                  Text('申根 26 国 (${_schengen.length})', style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
                ]),
                TextButton(
                  onPressed: () => setState(() => _schengenExpanded = !_schengenExpanded),
                  child: Text(_schengenExpanded ? '收起' : '展开'),
                ),
              ],
            ),
            const SizedBox(height: 12),
            if (_schengenExpanded) _schengenGrid(_schengen)
            else _schengenPreview(_schengen.take(6).toList()),
          ],
        ],
      ),
    );
  }

  Widget _heroCoverCard(Destination d) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        // W33: avoid LinearGradient on Flutter web canvas — solid color instead
        color: const Color(0xFFEFF6FF),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Row(
        children: [
          Text(_flagOf(d.countryCode), style: const TextStyle(fontSize: 36)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(d.countryName, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Color(0xFF0F172A))),
                const SizedBox(height: 4),
                Row(children: [
                  if (d.feeLabel.isNotEmpty) Text('FROM ${d.feeLabel}', style: const TextStyle(fontSize: 13, color: Color(0xFF3B6EF5), fontWeight: FontWeight.w700)),
                  if (d.feeLabel.isNotEmpty && d.validityLabel.isNotEmpty) const Text(' · ', style: TextStyle(color: Color(0xFF94A3B8))),
                  if (d.validityLabel.isNotEmpty) Text('VALID ${d.validityLabel}', style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
                ]),
              ],
            ),
          ),
          ElevatedButton(
            onPressed: () => _openApply(d),
            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF3B6EF5), padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8)),
            child: const Text('办签证', style: TextStyle(fontSize: 12)),
          ),
        ],
      ),
    );
  }

  Widget _schengenPreview(List<Destination> preview) {
    return Wrap(
      spacing: 8, runSpacing: 8,
      children: preview.map((d) => InkWell(
        onTap: () => _openApply(d),
        borderRadius: BorderRadius.circular(10),
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
          decoration: BoxDecoration(color: Colors.white, border: Border.all(color: const Color(0xFFE2E8F0)), borderRadius: BorderRadius.circular(10)),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Text(_flagOf(d.countryCode), style: const TextStyle(fontSize: 16)),
            const SizedBox(width: 4),
            Text(d.countryCode, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
          ]),
        ),
      )).toList(),
    );
  }

  Widget _schengenGrid(List<Destination> all) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(crossAxisCount: 4, crossAxisSpacing: 8, mainAxisSpacing: 8),
      itemCount: all.length,
      itemBuilder: (_, i) {
        final d = all[i];
        return InkWell(
          onTap: () => _openApply(d),
          borderRadius: BorderRadius.circular(10),
          child: Container(
            padding: const EdgeInsets.all(8),
            decoration: BoxDecoration(color: Colors.white, border: Border.all(color: const Color(0xFFE2E8F0)), borderRadius: BorderRadius.circular(10)),
            child: Column(
              mainAxisAlignment: MainAxisAlignment.center,
              children: [
                Text(_flagOf(d.countryCode), style: const TextStyle(fontSize: 28)),
                const SizedBox(height: 4),
                Text(d.countryCode, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w600)),
              ],
            ),
          ),
        );
      },
    );
  }

  String _flagOf(String cc) {
    const flags = {
      'US': '🇺🇸', 'JP': '🇯🇵', 'KR': '🇰🇷', 'SG': '🇸🇬', 'GB': '🇬🇧', 'FR': '🇫🇷',
      'ID': '🇮🇩', 'VN': '🇻🇳', 'TH': '🇹🇭', 'DE': '🇩🇪', 'AU': '🇦🇺', 'CA': '🇨🇦',
      'NZ': '🇳🇿', 'SCHENGEN': '🇪🇺',
      'AT': '🇦🇹', 'BE': '🇧🇪', 'HR': '🇭🇷', 'CZ': '🇨🇿', 'DK': '🇩🇰', 'EE': '🇪🇪',
      'FI': '🇫🇮', 'GR': '🇬🇷', 'HU': '🇭🇺', 'IS': '🇮🇸', 'IT': '🇮🇹', 'LV': '🇱🇻',
      'LI': '🇱🇮', 'LT': '🇱🇹', 'LU': '🇱🇺', 'MT': '🇲🇹', 'NL': '🇳🇱', 'NO': '🇳🇴',
      'PL': '🇵🇱', 'PT': '🇵🇹', 'SK': '🇸🇰', 'SI': '🇸🇮', 'ES': '🇪🇸', 'SE': '🇸🇪',
    };
    return flags[cc] ?? '🌐';
  }
}