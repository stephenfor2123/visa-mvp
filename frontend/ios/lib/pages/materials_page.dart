// Materials page — port of frontend/web/src/views/Materials.vue to Flutter (W8-1).
//
// Mirrors the web page on mobile:
// - 3 tabs (Photo / Upload File / Voice) — only Upload is interactive in W8-1,
//   Photo and Voice show a 'W2' notice so the visual structure stays complete.
// - MaterialUploader widget (drag/tap/progress/done) is the active uploader
// - Collected list shows 1 demo item on first render (matches web behavior).
// - Validate button + "Continue" button after validation.

import 'package:flutter/material.dart';

import '../l10n/generated/app_localizations.dart';
import '../widgets/material_uploader.dart';

class MaterialsPage extends StatefulWidget {
  const MaterialsPage({super.key});

  @override
  State<MaterialsPage> createState() => _MaterialsPageState();
}

class _MaterialsPageState extends State<MaterialsPage> {
  String _activeTab = 'photo';
  final List<MaterialItem> _items = [];
  bool _validating = false;
  bool _lastValidated = false;

  @override
  void initState() {
    super.initState();
    // Demo seed: show 1 item so the list is visible on first render — same
    // behavior as the web Materials.vue onMounted fallback.
    _items.add(const MaterialItem(
      id: 'mat_demo_passport',
      materialType: 'passport',
      fileName: 'passport_E1234567.jpg',
      fileSize: 412 * 1024,
      mimeType: 'image/jpeg',
      ocrStatus: 'done',
    ));
  }

  void _onCaptured(MaterialItem item) {
    setState(() {
      _items.insert(0, item);
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('✓ ${item.fileName}')),
    );
  }

  void _onDelete(MaterialItem item) {
    setState(() {
      _items.removeWhere((m) => m.id == item.id);
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('🗑 ${item.fileName}')),
    );
  }

  Future<void> _onValidate(AppLocalizations l) async {
    if (_items.isEmpty) return;
    setState(() => _validating = true);
    await Future.delayed(const Duration(milliseconds: 1200));
    if (!mounted) return;
    setState(() {
      _validating = false;
      _lastValidated = true;
    });
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text(l.toastMaterialsValidated)),
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        title: Text(l.materialsTitle),
        leading: IconButton(
          icon: const Icon(Icons.arrow_back),
          onPressed: () => Navigator.of(context).pop(),
        ),
      ),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(
                l.materialsSubtitle,
                style: const TextStyle(
                  fontSize: 13,
                  color: Color(0xFF5A5F6D),
                ),
              ),
              const SizedBox(height: 14),
              _buildTabs(l, theme),
              const SizedBox(height: 14),
              if (_activeTab == 'pdf') ...[
                MaterialUploader(onCaptured: _onCaptured),
              ] else if (_activeTab == 'photo') ...[
                _buildPhotoPanel(l, theme),
              ] else ...[
                _buildVoicePanel(l, theme),
              ],
              const SizedBox(height: 20),
              _buildListSection(l, theme),
              const SizedBox(height: 20),
              if (_items.isNotEmpty) _buildFooter(l, theme),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTabs(AppLocalizations l, ThemeData theme) {
    final tabs = [
      _Tab(key: 'photo', label: l.materialsTabPhoto, icon: Icons.camera_alt_outlined),
      _Tab(key: 'pdf', label: l.materialsTabPdf, icon: Icons.upload_file_outlined),
      _Tab(key: 'voice', label: l.materialsTabVoice, icon: Icons.mic_none_outlined),
    ];
    return Row(
      children: tabs.map((t) {
        final active = _activeTab == t.key;
        return Expanded(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            child: InkWell(
              borderRadius: BorderRadius.circular(10),
              onTap: () => setState(() => _activeTab = t.key),
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12),
                decoration: BoxDecoration(
                  color: active ? const Color(0xFFEAF0FE) : Colors.white,
                  borderRadius: BorderRadius.circular(10),
                  border: Border.all(
                    color: active
                        ? theme.colorScheme.primary
                        : const Color(0xFFE2E8F0),
                  ),
                ),
                child: Column(
                  children: [
                    Icon(
                      t.icon,
                      size: 22,
                      color: active
                          ? theme.colorScheme.primary
                          : const Color(0xFF334155),
                    ),
                    const SizedBox(height: 4),
                    Text(
                      t.label,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight:
                            active ? FontWeight.w600 : FontWeight.w500,
                        color: active
                            ? theme.colorScheme.primary
                            : const Color(0xFF334155),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ),
        );
      }).toList(),
    );
  }

  Widget _buildPhotoPanel(AppLocalizations l, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        children: [
          const Icon(Icons.photo_camera_outlined, size: 40, color: Color(0xFF3B6EF5)),
          const SizedBox(height: 8),
          const Text(
            'Photo capture — W2',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            l.materialsUploadDesc,
            style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildVoicePanel(AppLocalizations l, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.all(28),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: const Color(0xFFE2E8F0)),
      ),
      child: Column(
        children: [
          Container(
            width: 80,
            height: 80,
            decoration: const BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [Color(0xFF3B6EF5), Color(0xFF6E59F0)],
              ),
            ),
            child: const Icon(Icons.mic, color: Colors.white, size: 32),
          ),
          const SizedBox(height: 10),
          const Text(
            'Voice capture — W2',
            style: TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: Color(0xFF0F172A),
            ),
          ),
          const SizedBox(height: 4),
          Text(
            l.materialsSubtitle,
            style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
            textAlign: TextAlign.center,
          ),
        ],
      ),
    );
  }

  Widget _buildListSection(AppLocalizations l, ThemeData theme) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          children: [
            Text(
              '${l.materialsCollectedCount} (${_items.length})',
              style: const TextStyle(
                fontSize: 16,
                fontWeight: FontWeight.w600,
                color: Color(0xFF0F172A),
              ),
            ),
            const Spacer(),
            if (_lastValidated)
              Container(
                padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                decoration: BoxDecoration(
                  color: const Color(0xFFDCFCE7),
                  borderRadius: BorderRadius.circular(999),
                ),
                child: Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    const Icon(Icons.check, size: 12, color: Color(0xFF166534)),
                    const SizedBox(width: 2),
                    Text(
                      l.materialsOcrDone,
                      style: const TextStyle(
                        fontSize: 12,
                        color: Color(0xFF166534),
                        fontWeight: FontWeight.w500,
                      ),
                    ),
                  ],
                ),
              ),
          ],
        ),
        const SizedBox(height: 10),
        if (_items.isEmpty)
          Container(
            padding: const EdgeInsets.symmetric(vertical: 32, horizontal: 16),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(12),
              border: Border.all(
                color: const Color(0xFFE2E8F0),
                style: BorderStyle.solid,
              ),
            ),
            child: Column(
              children: [
                const Icon(Icons.folder_open, size: 40, color: Color(0xFF94A3B8)),
                const SizedBox(height: 6),
                Text(
                  l.materialsEmptyTitle,
                  style: const TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: Color(0xFF0F172A),
                  ),
                ),
                const SizedBox(height: 2),
                Text(
                  l.materialsEmptyDesc,
                  style: const TextStyle(
                    fontSize: 12,
                    color: Color(0xFF64748B),
                  ),
                ),
              ],
            ),
          )
        else
          ..._items.map((m) => _buildItemCard(m, l, theme)),
      ],
    );
  }

  Widget _buildItemCard(MaterialItem m, AppLocalizations l, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Container(
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: const Color(0xFFE2E8F0)),
        ),
        child: Row(
          children: [
            Container(
              width: 56,
              height: 70,
              decoration: BoxDecoration(
                color: const Color(0xFFF1F5F9),
                borderRadius: BorderRadius.circular(8),
              ),
              child: const Icon(
                Icons.description_outlined,
                size: 28,
                color: Color(0xFF94A3B8),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    m.fileName,
                    style: const TextStyle(
                      fontSize: 14,
                      fontWeight: FontWeight.w500,
                      color: Color(0xFF0F172A),
                    ),
                    overflow: TextOverflow.ellipsis,
                  ),
                  const SizedBox(height: 4),
                  Row(
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                            horizontal: 6, vertical: 2),
                        decoration: BoxDecoration(
                          color: const Color(0xFFEAF0FE),
                          borderRadius: BorderRadius.circular(999),
                        ),
                        child: Text(
                          _typeLabel(m.materialType, l),
                          style: const TextStyle(
                            fontSize: 11,
                            color: Color(0xFF2D5BFF),
                          ),
                        ),
                      ),
                      const SizedBox(width: 6),
                      Text(
                        _formatSize(m.fileSize),
                        style: const TextStyle(
                          fontSize: 11,
                          color: Color(0xFF64748B),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  _buildStatusBadge(m.ocrStatus, l),
                ],
              ),
            ),
            IconButton(
              icon: const Icon(Icons.delete_outline, color: Color(0xFF94A3B8)),
              onPressed: () => _onDelete(m),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStatusBadge(String status, AppLocalizations l) {
    final mapping = {
      'done': (l.materialsOcrDone, const Color(0xFFDCFCE7), const Color(0xFF166534)),
      'processing': (l.materialsOcrProcessing, const Color(0xFFDBEAFE), const Color(0xFF1E40AF)),
      'failed': (l.materialsOcrFailed, const Color(0xFFFEE2E2), const Color(0xFFB91C1C)),
      'pending': (l.materialsOcrPending, const Color(0xFFFEF3C7), const Color(0xFFB45309)),
    };
    final (text, bg, fg) = mapping[status] ??
        (l.materialsOcrPending, const Color(0xFFFEF3C7), const Color(0xFFB45309));
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        text,
        style: TextStyle(
          fontSize: 11,
          color: fg,
          fontWeight: FontWeight.w500,
        ),
      ),
    );
  }

  Widget _buildFooter(AppLocalizations l, ThemeData theme) {
    return Row(
      children: [
        Expanded(
          child: FilledButton(
            onPressed: _validating ? null : () => _onValidate(l),
            style: FilledButton.styleFrom(
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
            child: _validating
                ? SizedBox(
                    height: 18,
                    width: 18,
                    child: CircularProgressIndicator(
                      strokeWidth: 2,
                      color: theme.colorScheme.onPrimary,
                    ),
                  )
                : Text(
                    _validating
                        ? l.materialsValidating
                        : l.materialsValidateBtn,
                  ),
          ),
        ),
        if (_lastValidated) ...[
          const SizedBox(width: 10),
          Expanded(
            child: OutlinedButton(
              onPressed: () {
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('${l.materialsContinueBtn} →')),
                );
              },
              style: OutlinedButton.styleFrom(
                padding: const EdgeInsets.symmetric(vertical: 14),
              ),
              child: Text('${l.materialsContinueBtn} →'),
            ),
          ),
        ],
      ],
    );
  }

  String _typeLabel(String type, AppLocalizations l) {
    switch (type) {
      case 'passport':
        return l.materialsTypePassport;
      case 'photo':
        return l.materialsTypePhoto;
      case 'proof':
        return l.materialsTypeProof;
      default:
        return l.materialsTypeOther;
    }
  }

  String _formatSize(int bytes) {
    if (bytes <= 0) return '';
    if (bytes > 1024 * 1024) {
      return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    }
    return '${(bytes / 1024).round()} KB';
  }
}

class _Tab {
  final String key;
  final String label;
  final IconData icon;
  const _Tab({required this.key, required this.label, required this.icon});
}
