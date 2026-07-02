// SelfieCapture widget — lightweight self-portrait capture (W32 port).
//
// Used inside Apply flow for identity verification step. Real implementation
// uses camera; this version supports a manual "已上传" toggle for tests.

import 'dart:io';
import 'package:flutter/material.dart';

class SelfieCapture extends StatefulWidget {
  final void Function(File? file)? onCaptured;
  const SelfieCapture({super.key, this.onCaptured});

  @override
  State<SelfieCapture> createState() => _SelfieCaptureState();
}

class _SelfieCaptureState extends State<SelfieCapture> {
  File? _file;
  bool _captured = false;

  void _mockCapture() {
    setState(() {
      _captured = true;
    });
    widget.onCaptured?.call(null);
  }

  void _reset() {
    setState(() {
      _file = null;
      _captured = false;
    });
    widget.onCaptured?.call(null);
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        AspectRatio(
          aspectRatio: 3 / 4,
          child: Container(
            decoration: BoxDecoration(
              color: const Color(0xFFF1F5F9),
              borderRadius: BorderRadius.circular(16),
              border: Border.all(color: const Color(0xFFCBD5E1), width: 1.5),
            ),
            child: _captured
                ? const Center(child: Icon(Icons.check_circle, size: 64, color: Color(0xFF10B981)))
                : Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: const [
                      Icon(Icons.face_outlined, size: 64, color: Color(0xFF94A3B8)),
                      SizedBox(height: 12),
                      Text('点击下方按钮开始自拍', style: TextStyle(fontSize: 13, color: Color(0xFF64748B))),
                    ],
                  ),
          ),
        ),
        const SizedBox(height: 12),
        if (_captured)
          OutlinedButton.icon(
            onPressed: _reset,
            icon: const Icon(Icons.refresh),
            label: const Text('重拍'),
            style: OutlinedButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 14)),
          )
        else
          ElevatedButton.icon(
            onPressed: _mockCapture,
            icon: const Icon(Icons.camera_alt),
            label: const Text('开始自拍'),
            style: ElevatedButton.styleFrom(
              backgroundColor: const Color(0xFF3B6EF5),
              padding: const EdgeInsets.symmetric(vertical: 14),
            ),
          ),
      ],
    );
  }
}