// Destinations page — W13 Flutter iOS port of miniprogram/pages/destinations/.
//
// Shows all available visa destinations in a scrollable grid.
// Mock data: static country list (API integration in V2.1).
// Each card shows flag + country name + visa type chips + Apply button.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class DestinationsPage extends StatefulWidget {
  const DestinationsPage({super.key});

  @override
  State<DestinationsPage> createState() => _DestinationsPageState();
}

class _DestinationsPageState extends State<DestinationsPage> {
  bool _loading = false;
  String? _error;

  static final List<Map<String, dynamic>> _destinations = [
    {'code': 'TH', 'name': 'Thailand', 'nameZh': '泰国', 'nameId': 'Thailand', 'nameVi': 'Thái Lan', 'types': ['旅游签', '学生签'], 'enabled': true},
    {'code': 'VN', 'name': 'Vietnam', 'nameZh': '越南', 'nameId': 'Vietnam', 'nameVi': 'Việt Nam', 'types': ['旅游签'], 'enabled': true},
    {'code': 'ID', 'name': 'Indonesia', 'nameZh': '印度尼西亚', 'nameId': 'Indonesia', 'nameVi': 'Indonesia', 'types': ['旅游签'], 'enabled': true},
    {'code': 'PH', 'name': 'Philippines', 'nameZh': '菲律宾', 'nameId': 'Filipina', 'nameVi': 'Philippines', 'types': ['旅游签'], 'enabled': true},
    {'code': 'MY', 'name': 'Malaysia', 'nameZh': '马来西亚', 'nameId': 'Malaysia', 'nameVi': 'Malaysia', 'types': ['旅游签', '学生签'], 'enabled': true},
    {'code': 'SG', 'name': 'Singapore', 'nameZh': '新加坡', 'nameId': 'Singapura', 'nameVi': 'Singapore', 'types': ['旅游签'], 'enabled': true},
    {'code': 'JP', 'name': 'Japan', 'nameZh': '日本', 'nameId': 'Jepang', 'nameVi': 'Nhật Bản', 'types': ['旅游签', '学生签'], 'enabled': false},
    {'code': 'KR', 'name': 'South Korea', 'nameZh': '韩国', 'nameId': 'Korea Selatan', 'nameVi': 'Hàn Quốc', 'types': ['旅游签'], 'enabled': false},
    {'code': 'AU', 'name': 'Australia', 'nameZh': '澳大利亚', 'nameId': 'Australia', 'nameVi': 'Úc', 'types': ['旅游签', '学生签'], 'enabled': false},
    {'code': 'GB', 'name': 'United Kingdom', 'nameZh': '英国', 'nameId': 'Inggris', 'nameVi': 'Anh', 'types': ['旅游签', '学生签'], 'enabled': false},
    {'code': 'DE', 'name': 'Germany', 'nameZh': '德国', 'nameId': 'Jerman', 'nameVi': 'Đức', 'types': ['旅游签', '申根签'], 'enabled': false},
    {'code': 'FR', 'name': 'France', 'nameZh': '法国', 'nameId': 'Prancis', 'nameVi': 'Pháp', 'types': ['旅游签', '申根签'], 'enabled': false},
  ];

  String _countryName(Map<String, dynamic> d) {
    final l = AppLocalizations.of(context)!;
    final code = l.localeName;
    if (code.startsWith('zh')) return d['nameZh'] as String;
    if (code == 'id') return d['nameId'] as String;
    if (code == 'vi') return d['nameVi'] as String;
    return d['name'] as String;
  }

  String _flag(String code) {
    if (code.isEmpty) return '🌐';
    return code.toUpperCase().split('').map((c) => String.fromCharCode(0x1f1e6 + c.codeUnitAt(0) - 65)).join();
  }

  void _onApply(Map<String, dynamic> dest) {
    if (!(dest['enabled'] as bool)) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(AppLocalizations.of(context)!.destComingSoon),
          backgroundColor: Colors.orange,
        ),
      );
      return;
    }
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text('${_countryName(dest)} — ${AppLocalizations.of(context)!.destApplyNow}'),
        backgroundColor: const Color(0xFF3B6EF5),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        title: Row(
          children: [
            Container(
              width: 28, height: 28,
              decoration: BoxDecoration(
                gradient: const LinearGradient(colors: [Color(0xFF3B6EF5), Color(0xFF6E59F0)]),
                borderRadius: BorderRadius.circular(6),
              ),
              alignment: Alignment.center,
              child: const Text('V', style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 14)),
            ),
            const SizedBox(width: 8),
            Text(l.commonAppName, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.language, color: Color(0xFF6B7280)),
            onPressed: () => _showLanguageSheet(context),
          ),
        ],
      ),
      body: SafeArea(
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.destTitle, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: Color(0xFF1A1A2E))),
                  const SizedBox(height: 4),
                  Text(l.destSubtitle, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
                ],
              ),
            ),
            Expanded(
              child: GridView.builder(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
                  crossAxisCount: 2,
                  mainAxisSpacing: 12,
                  crossAxisSpacing: 12,
                  childAspectRatio: 0.88,
                ),
                itemCount: _destinations.length,
                itemBuilder: (ctx, i) {
                  final d = _destinations[i];
                  final enabled = d['enabled'] as bool;
                  final types = (d['types'] as List).cast<String>();
                  return _DestinationCard(
                    flag: _flag(d['code'] as String),
                    name: _countryName(d),
                    types: types,
                    enabled: enabled,
                    l: l,
                    onApply: () => _onApply(d),
                  );
                },
              ),
            ),
          ],
        ),
      ),
    );
  }

  void _showLanguageSheet(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    showModalBottomSheet(
      context: context,
      builder: (_) => Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          ListTile(title: Text(l.languageZh), onTap: () { Navigator.pop(context); _setLocale(context, const Locale('zh')); }),
          ListTile(title: Text(l.languageEn), onTap: () { Navigator.pop(context); _setLocale(context, const Locale('en')); }),
          ListTile(title: Text(l.languageId), onTap: () { Navigator.pop(context); _setLocale(context, const Locale('id')); }),
          ListTile(title: Text(l.languageVi), onTap: () { Navigator.pop(context); _setLocale(context, const Locale('vi')); }),
          const SizedBox(height: 16),
        ],
      ),
    );
  }

  void _setLocale(BuildContext context, Locale locale) {
    // Trigger locale change by navigating home with new locale
    Navigator.pushNamedAndRemoveUntil(context, AppRoutes.home, (r) => false);
  }
}

class _DestinationCard extends StatelessWidget {
  final String flag;
  final String name;
  final List<String> types;
  final bool enabled;
  final AppLocalizations l;
  final VoidCallback onApply;

  const _DestinationCard({
    required this.flag, required this.name, required this.types,
    required this.enabled, required this.l, required this.onApply,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, 2))],
        border: enabled ? null : Border.all(color: Colors.grey.shade300),
      ),
      child: Opacity(
        opacity: enabled ? 1.0 : 0.55,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(flag, style: const TextStyle(fontSize: 36)),
              const SizedBox(height: 8),
              Text(name, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF1A1A2E)), maxLines: 1, overflow: TextOverflow.ellipsis),
              const SizedBox(height: 6),
              Expanded(
                child: Wrap(
                  spacing: 4,
                  runSpacing: 4,
                  children: types.map((t) => Container(
                    padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                    decoration: BoxDecoration(
                      color: const Color(0xFFEEF2FF),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: Text(t, style: const TextStyle(fontSize: 11, color: Color(0xFF3B6EF5))),
                  )).toList(),
                ),
              ),
              const SizedBox(height: 8),
              SizedBox(
                width: double.infinity,
                child: ElevatedButton(
                  onPressed: enabled ? onApply : null,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: enabled ? const Color(0xFF3B6EF5) : Colors.grey.shade300,
                    foregroundColor: Colors.white,
                    elevation: 0,
                    shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)),
                    padding: const EdgeInsets.symmetric(vertical: 8),
                  ),
                  child: Text(
                    enabled ? l.destApplyNow : l.destComingSoon,
                    style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w600),
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
