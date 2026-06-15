// MaterialUploader widget — port of frontend/web/src/components/MaterialUploader.vue
// to Flutter (W8-1).
//
// Behavior:
// - Tap the dropzone to open a system file picker
// - Drag a file onto the dropzone (desktop / web only — mobile has no native drag
//   but the gesture is harmless)
// - 3 phases: idle (CTA) / uploading (progress bar 0-100%) / done (preview)
// - On accept the widget calls `onCaptured(MaterialItem)` so the parent page can
//   prepend it to the list; the parent can also delete the file via the returned
//   id.
//
// We do NOT actually upload bytes here — the backend media upload endpoint
// requires multipart + auth wiring that is W2 scope. For W8-1 we synthesize a
// local MaterialItem with a fake id and a placeholder thumbnail.

import 'dart:async';
import 'package:flutter/material.dart';

import '../l10n/generated/app_localizations.dart';

class MaterialItem {
  final String id;
  final String materialType; // passport / photo / proof / other
  final String fileName;
  final int fileSize;
  final String mimeType;
  final String ocrStatus; // pending / processing / done / failed

  const MaterialItem({
    required this.id,
    required this.materialType,
    required this.fileName,
    required this.fileSize,
    required this.mimeType,
    required this.ocrStatus,
  });
}

class MaterialUploader extends StatefulWidget {
  final ValueChanged<MaterialItem> onCaptured;
  final List<String> acceptTypes;
  final int maxBytes;
  final String defaultType;

  const MaterialUploader({
    super.key,
    required this.onCaptured,
    this.acceptTypes = const ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'],
    this.maxBytes = 10 * 1024 * 1024,
    this.defaultType = 'passport',
  });

  @override
  State<MaterialUploader> createState() => _MaterialUploaderState();
}

class _MaterialUploaderState extends State<MaterialUploader> {
  String _phase = 'idle'; // idle | uploading | done
  String _uploadingName = '';
  String _doneName = '';
  int _progress = 0;
  int _uploadedCount = 0;
  Timer? _ticker;

  @override
  void dispose() {
    _ticker?.cancel();
    super.dispose();
  }

  String _guessType(String fileName) {
    final lower = fileName.toLowerCase();
    if (lower.contains('passport')) return 'passport';
    if (lower.contains('photo') || lower.contains('img')) return 'photo';
    if (lower.contains('proof') ||
        lower.contains('bank') ||
        lower.contains('letter')) {
      return 'proof';
    }
    return widget.defaultType;
  }

  Future<void> _simulateUpload(String fileName, int fileSize, String mime) async {
    setState(() {
      _phase = 'uploading';
      _uploadingName = fileName;
      _progress = 0;
    });
    _ticker?.cancel();
    _ticker = Timer.periodic(const Duration(milliseconds: 120), (t) {
      if (!mounted) {
        t.cancel();
        return;
      }
      setState(() {
        if (_progress < 88) {
          _progress = (_progress + 12).clamp(0, 100);
        }
      });
    });
    // Simulate network latency.
    await Future.delayed(const Duration(milliseconds: 1400));
    _ticker?.cancel();
    if (!mounted) return;
    setState(() {
      _progress = 100;
      _phase = 'done';
      _doneName = fileName;
      _uploadedCount += 1;
    });
    widget.onCaptured(MaterialItem(
      id: 'mat_${DateTime.now().millisecondsSinceEpoch}',
      materialType: _guessType(fileName),
      fileName: fileName,
      fileSize: fileSize,
      mimeType: mime,
      ocrStatus: 'processing',
    ));
  }

  Future<void> _onPickFile() async {
    // We don't pull file_picker / image_picker in W8-1 — the parent is shown
    // a synthetic item via _simulateUpload so the flow is testable.
    final name = 'passport_E${DateTime.now().millisecondsSinceEpoch % 10000000}.jpg';
    await _simulateUpload(name, 412 * 1024, 'image/jpeg');
  }

  Future<void> _onDroppedFile() async {
    // Mobile has no native drag — but a 'drop' event from desktop is harmless.
    // We simulate the same flow.
    await _onPickFile();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);

    return DragTarget<String>(
      onAcceptWithDetails: (_) => _onDroppedFile(),
      builder: (context, candidate, rejected) {
        final hover = candidate.isNotEmpty;
        return GestureDetector(
          onTap: _onPickFile,
          child: Container(
            width: double.infinity,
            padding: const EdgeInsets.symmetric(vertical: 28, horizontal: 20),
            decoration: BoxDecoration(
              color: hover ? const Color(0xFFF0F4FF) : Colors.white,
              borderRadius: BorderRadius.circular(16),
              border: Border.all(
                color: hover
                    ? theme.colorScheme.primary
                    : const Color(0xFFCBD5E1),
                width: 2,
                style: BorderStyle.solid,
              ),
            ),
            child: _buildContent(l, theme),
          ),
        );
      },
    );
  }

  Widget _buildContent(AppLocalizations l, ThemeData theme) {
    if (_phase == 'uploading') {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          const Icon(Icons.hourglass_top, size: 40, color: Color(0xFF3B6EF5)),
          const SizedBox(height: 8),
          Text(
            _uploadingName,
            style: const TextStyle(
              fontSize: 14,
              fontWeight: FontWeight.w600,
              color: Color(0xFF0F172A),
            ),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 10),
          SizedBox(
            width: 220,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(3),
              child: LinearProgressIndicator(
                value: _progress / 100,
                minHeight: 6,
                backgroundColor: const Color(0xFFE2E8F0),
                valueColor: const AlwaysStoppedAnimation<Color>(
                  Color(0xFF3B6EF5),
                ),
              ),
            ),
          ),
          const SizedBox(height: 6),
          Text(
            '$_progress%',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: Color(0xFF3B6EF5),
            ),
          ),
        ],
      );
    }
    if (_phase == 'done') {
      return Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 64,
            height: 80,
            decoration: BoxDecoration(
              color: const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(8),
            ),
            child: const Icon(
              Icons.description_outlined,
              size: 32,
              color: Color(0xFF94A3B8),
            ),
          ),
          const SizedBox(height: 8),
          Text(
            _doneName,
            style: const TextStyle(
              fontSize: 13,
              fontWeight: FontWeight.w500,
              color: Color(0xFF0F172A),
            ),
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 2),
          Text(
            '${l.materialsUploadedOk} · $_uploadedCount',
            style: const TextStyle(
              fontSize: 12,
              color: Color(0xFF16A34A),
              fontWeight: FontWeight.w500,
            ),
          ),
        ],
      );
    }
    // idle
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        const Icon(Icons.cloud_upload_outlined, size: 40, color: Color(0xFF3B6EF5)),
        const SizedBox(height: 8),
        Text(
          l.materialsUploadTitle,
          style: const TextStyle(
            fontSize: 15,
            fontWeight: FontWeight.w600,
            color: Color(0xFF0F172A),
          ),
        ),
        const SizedBox(height: 2),
        Text(
          l.materialsUploadDesc,
          style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
        ),
        const SizedBox(height: 8),
        Wrap(
          alignment: WrapAlignment.center,
          crossAxisAlignment: WrapCrossAlignment.center,
          spacing: 4,
          children: [
            Text(
              l.materialsFormatHint,
              style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
            ),
            const Text(
              '·',
              style: TextStyle(fontSize: 11, color: Color(0xFFCBD5E1)),
            ),
            Text(
              l.materialsSizeHint,
              style: const TextStyle(fontSize: 11, color: Color(0xFF94A3B8)),
            ),
          ],
        ),
      ],
    );
  }
}
