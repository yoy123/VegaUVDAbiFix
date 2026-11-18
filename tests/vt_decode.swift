import Foundation
import VideoToolbox
import AVFoundation

print("H264 HW supported:", VTIsHardwareDecodeSupported(kCMVideoCodecType_H264))
print("HEVC HW supported:", VTIsHardwareDecodeSupported(kCMVideoCodecType_HEVC))

func decode(_ path: String) async {
    let asset = AVURLAsset(url: URL(fileURLWithPath: path))
    guard let track = try? await asset.loadTracks(withMediaType: .video).first,
          let format = try? await track.load(.formatDescriptions).first else {
        print("No track/format description:", path)
        return
    }
    let spec: [String: Any] = [
        kVTVideoDecoderSpecification_RequireHardwareAcceleratedVideoDecoder as String: true
    ]
    var session: VTDecompressionSession?
    let status = VTDecompressionSessionCreate(
        allocator: nil,
        formatDescription: format,
        decoderSpecification: spec as CFDictionary,
        imageBufferAttributes: nil,
        outputCallback: nil,
        decompressionSessionOut: &session
    )
    print("HW decode \(URL(fileURLWithPath: path).lastPathComponent): \(status)")
    if let session { VTDecompressionSessionInvalidate(session) }
}

let sem = DispatchSemaphore(value: 0)
Task {
    await decode(CommandLine.arguments.count > 1 ? CommandLine.arguments[1] : "/tmp/vt_in.mp4")
    await decode(CommandLine.arguments.count > 2 ? CommandLine.arguments[2] : "/tmp/vt_hevc.mp4")
    sem.signal()
}
sem.wait()
