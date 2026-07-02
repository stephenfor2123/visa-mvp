// CountrySearchModal — searchable country picker modal.
//
// Used when there are too many countries to fit on screen, or when user
// wants to quickly jump to a specific destination (e.g. typing "FR").

import 'package:flutter/material.dart';
import '../services/destinations_service.dart';

class CountrySearchModal extends StatefulWidget {
  final List<Destination> countries;
  final void Function(Destination) onSelect;
  const CountrySearchModal({super.key, required this.countries, required this.onSelect});

  static Future<void> show(BuildContext context, {
    required List<Destination> countries,
    required void Function(Destination) onSelect,
  }) {
    return showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      backgroundColor: Colors.white,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(16))),
      builder: (_) => CountrySearchModal(countries: countries, onSelect: onSelect),
    );
  }

  @override
  State<CountrySearchModal> createState() => _CountrySearchModalState();
}

class _CountrySearchModalState extends State<CountrySearchModal> {
  final _ctrl = TextEditingController();
  String _q = '';

  @override
  void dispose() {
    _ctrl.dispose();
    super.dispose();
  }

  List<Destination> get _filtered {
    if (_q.isEmpty) return widget.countries;
    final q = _q.toLowerCase();
    return widget.countries.where((d) =>
        d.countryName.toLowerCase().contains(q) ||
        d.countryCode.toLowerCase().contains(q)).toList();
  }

  @override
  Widget build(BuildContext context) {
    final filtered = _filtered;
    return DraggableScrollableSheet(
      expand: false,
      initialChildSize: 0.85,
      maxChildSize: 0.95,
      minChildSize: 0.5,
      builder: (_, controller) => Column(
        children: [
          Container(
            width: 36, height: 4, margin: const EdgeInsets.only(top: 12, bottom: 12),
            decoration: BoxDecoration(color: const Color(0xFFE2E8F0), borderRadius: BorderRadius.circular(2)),
          ),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 16),
            child: TextField(
              controller: _ctrl,
              autofocus: true,
              decoration: const InputDecoration(
                prefixIcon: Icon(Icons.search),
                hintText: '搜索国家名或代码',
                border: OutlineInputBorder(),
              ),
              onChanged: (v) => setState(() => _q = v),
            ),
          ),
          const SizedBox(height: 12),
          Expanded(
            child: ListView.builder(
              controller: controller,
              itemCount: filtered.length,
              itemBuilder: (_, i) {
                final d = filtered[i];
                return ListTile(
                  leading: Text(_flagOf(d.countryCode), style: const TextStyle(fontSize: 24)),
                  title: Text(d.countryName),
                  subtitle: Text(d.countryCode),
                  trailing: d.enabled
                      ? const Icon(Icons.check_circle_outline, size: 16, color: Color(0xFF10B981))
                      : const Icon(Icons.lock_outline, size: 16, color: Color(0xFF94A3B8)),
                  onTap: () {
                    Navigator.of(context).pop();
                    widget.onSelect(d);
                  },
                );
              },
            ),
          ),
        ],
      ),
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