// MaterialsUpload page — W14 Flutter iOS port.
//
// Camera / gallery picker for uploading passport scan, photo, and other
// supporting documents. Shows upload progress + OCR status per file.
// Mock implementation; real image picker + OCR integration in V2.1.

import 'package:flutter/material.dart';
import '../l10n/generated/app_localizations.dart';
import '../main.dart';

class MaterialsUploadPage extends StatefulWidget {
  final String? orderNo;
  const MaterialsUploadPage({super.key, this.orderNo});

  @override
  State<MaterialsUploadPage> createState() => _MaterialsUploadPageState();
}

class _MaterialsUploadPageState extends State<MaterialsUploadPage> {
  final List<_UploadedFile> _files = [];

  void _onPickImage() {
    // Mock: add a dummy file after 500ms
    Future.delayed(const Duration(milliseconds: 500), () {
      if (!mounted) return;
      setState(() {
        _files.add(_UploadedFile(
          name: 'passport_scan_${_files.length + 1}.jpg',
          type: 'passport',
          status: 'uploading',
          size: 1024 * 512,
        ));
      });
      // Simulate upload progress
      _simulateUpload(_files.length - 1);
    });
  }

  void _simulateUpload(int idx) {
    Future.delayed(const Duration(milliseconds: 1200), () {
      if (!mounted || idx >= _files.length) return;
      setState(() {
        if (idx < _files.length) {
          _files[idx] = _files[idx].copyWith(status: 'ocr');
        }
      });
      // Simulate OCR
      Future.delayed(const Duration(milliseconds: 800), () {
        if (!mounted || idx >= _files.length) return;
        setState(() {
          if (idx < _files.length) {
            _files[idx] = _files[idx].copyWith(status: 'done');
          }
        });
      });
    });
  }

  void _onRemove(int idx) {
    setState(() => _files.removeAt(idx));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context)!;
    return Scaffold(
      backgroundColor: const Color(0xFFFAFBFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back, color: Color(0xFF1A1A2E)),
          onPressed: () => Navigator.pop(context),
        ),
        title: Text(l.materialsTitle, style: const TextStyle(color: Color(0xFF1A1A2E), fontWeight: FontWeight.w600, fontSize: 16)),
      ),
      body: SafeArea(
        child: Column(
          children: [
            // Header
            Container(
              width: double.infinity,
              padding: const EdgeInsets.all(16),
              color: Colors.white,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(l.materialsSubtitle, style: const TextStyle(fontSize: 14, color: Color(0xFF6B7280))),
                  const SizedBox(height: 12),
                  // Upload zone
                  GestureDetector(
                    onTap: _onPickImage,
                    child: Container(
                      width: double.infinity,
                      padding: const EdgeInsets.symmetric(vertical: 32),
                      decoration: BoxDecoration(
                        color: const Color(0xFFF3F4F6),
                        borderRadius: BorderRadius.circular(12),
                        border: Border.all(color: const Color(0xFFE5E7EB), style: BorderStyle.solid),
                      ),
                      child: Column(
                        children: [
                          Container(
                            width: 48, height: 48,
                            decoration: BoxDecoration(
                              color: const Color(0xFFEEF2FF),
                              borderRadius: BorderRadius.circular(24),
                            ),
                            child: const Icon(Icons.cloud_upload_outlined, size: 24, color: Color(0xFF3B6EF5)),
                          ),
                          const SizedBox(height: 10),
                          Text(l.materialsUploadTitle, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500, color: Color(0xFF1A1A2E))),
                          const SizedBox(height: 4),
                          Text(l.materialsUploadDesc, style: const TextStyle(fontSize: 12, color: Color(0xFF9CA3AF))),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
            // File list
            Expanded(
              child: _files.isEmpty
                  ? Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          const Icon(Icons.folder_open, size: 48, color: Color(0xFF9CA3AF)),
                          const SizedBox(height: 12),
                          Text(l.materialsEmptyTitle, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w600, color: Color(0xFF6B7280))),
                          const SizedBox(height: 4),
                          Text(l.materialsEmptyDesc, style: const TextStyle(fontSize: 14, color: Color(0xFF9CA3AF))),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.all(16),
                      itemCount: _files.length,
                      itemBuilder: (ctx, i) => _FileCard(
                        file: _files[i],
                        l: l,
                        onRemove: () => _onRemove(i),
                      ),
                    ),
            ),
            // Bottom CTA
            if (_files.isNotEmpty)
              Container(
                padding: const EdgeInsets.all(16),
                decoration: BoxDecoration(
                  color: Colors.white,
                  boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.06), blurRadius: 8, offset: const Offset(0, -2))],
                ),
                child: SafeArea(
                  top: false,
                  child: Row(
                    children: [
                      Expanded(
                        child: OutlinedButton(
                          onPressed: _onPickImage,
                          style: OutlinedButton.styleFrom(
                            foregroundColor: const Color(0xFF3B6EF5),
                            side: const BorderSide(color: Color(0xFF3B6EF5)),
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          child: Text(l.materialsEmptyCta),
                        ),
                      ),
                      const SizedBox(width: 12),
                      Expanded(
                        flex: 2,
                        child: ElevatedButton(
                          onPressed: () {
                            ScaffoldMessenger.of(context).showSnackBar(
                              SnackBar(content: Text(l.materialsContinueBtn), backgroundColor: Colors.green),
                            );
                            Navigator.pushNamed(context, AppRoutes.orderForm);
                          },
                          style: ElevatedButton.styleFrom(
                            backgroundColor: const Color(0xFF3B6EF5),
                            foregroundColor: Colors.white,
                            elevation: 0,
                            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                            padding: const EdgeInsets.symmetric(vertical: 14),
                          ),
                          child: Text(l.materialsContinueBtn, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600)),
                        ),
                      ),
                    ],
                  ),
                ),
              ),
          ],
        ),
      ),
    );
  }
}

class _UploadedFile {
  final String name;
  final String type;
  final String status; // uploading / ocr / done / error
  final int size;

  const _UploadedFile({required this.name, required this.type, required this.status, required this.size});

  _UploadedFile copyWith({String? status}) {
    return _UploadedFile(name: name, type: type, status: status ?? this.status, size: size);
  }
}

class _FileCard extends StatelessWidget {
  final _UploadedFile file;
  final AppLocalizations l;
  final VoidCallback onRemove;

  const _FileCard({required this.file, required this.l, required this.onRemove});

  IconData get _typeIcon {
    switch (file.type) {
      case 'passport': return Icons.book;
      case 'photo': return Icons.photo_camera;
      case 'proof': return Icons.description;
      default: return Icons.insert_drive_file;
    }
  }

  String get _typeLabel {
    switch (file.type) {
      case 'passport': return l.materialsTypePassport;
      case 'photo': return l.materialsTypePhoto;
      case 'proof': return l.materialsTypeProof;
      default: return l.materialsTypeOther;
    }
  }

  String get _statusLabel {
    switch (file.status) {
      case 'uploading': return l.materialsUploading;
      case 'ocr': return l.materialsOcrProcessing;
      case 'done': return l.materialsOcrDone;
      case 'error': return l.materialsOcrFailed;
      default: return file.status;
    }
  }

  Color get _statusColor {
    switch (file.status) {
      case 'uploading': return const Color(0xFF3B6EF5);
      case 'ocr': return const Color(0xFFF59E0B);
      case 'done': return const Color(0xFF10B981);
      case 'error': return const Color(0xFFEF4444);
      default: return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 4)],
      ),
      child: Row(
        children: [
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              color: const Color(0xFFEEF2FF),
              borderRadius: BorderRadius.circular(8),
            ),
            child: Icon(_typeIcon, size: 20, color: const Color(0xFF3B6EF5)),
          ),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(file.name, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w500, color: Color(0xFF1A1A2E)), maxLines: 1, overflow: TextOverflow.ellipsis),
                const SizedBox(height: 2),
                Row(
                  children: [
                    Text(_typeLabel, style: const TextStyle(fontSize: 11, color: Color(0xFF9CA3AF))),
                    const SizedBox(width: 8),
                    Container(
                      padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 1),
                      decoration: BoxDecoration(color: _statusColor.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(4)),
                      child: Text(_statusLabel, style: TextStyle(fontSize: 11, color: _statusColor)),
                    ),
                  ],
                ),
                if (file.status == 'uploading') ...[
                  const SizedBox(height: 6),
                  LinearProgressIndicator(
                    value: null,
                    backgroundColor: const Color(0xFFE5E7EB),
                    valueColor: const AlwaysStoppedAnimation<Color>(Color(0xFF3B6EF5)),
                    minHeight: 2,
                  ),
                ],
              ],
            ),
          ),
          if (file.status != 'uploading')
            IconButton(
              icon: const Icon(Icons.delete_outline, size: 20, color: Color(0xFFEF4444)),
              onPressed: onRemove,
            ),
        ],
      ),
    );
  }
}