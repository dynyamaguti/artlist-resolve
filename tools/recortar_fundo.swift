// Recorta o fundo de uma foto (pessoa/objeto em primeiro plano) usando o Vision do macOS 14+.
// Uso: swiftc -O recortar_fundo.swift -o recortar_fundo && ./recortar_fundo entrada.jpg saida.png
import Foundation
import Vision
import CoreImage
import AppKit

guard CommandLine.arguments.count >= 3 else {
    FileHandle.standardError.write("uso: recortar_fundo <entrada> <saida.png>\n".data(using: .utf8)!)
    exit(2)
}
let inURL = URL(fileURLWithPath: CommandLine.arguments[1])
let outURL = URL(fileURLWithPath: CommandLine.arguments[2])

guard let input = CIImage(contentsOf: inURL, options: [.applyOrientationProperty: true]) else {
    FileHandle.standardError.write("não consegui abrir a imagem\n".data(using: .utf8)!)
    exit(1)
}

let request = VNGenerateForegroundInstanceMaskRequest()
let handler = VNImageRequestHandler(ciImage: input, options: [:])
do { try handler.perform([request]) } catch {
    FileHandle.standardError.write("falha no Vision: \(error)\n".data(using: .utf8)!)
    exit(1)
}
guard let result = request.results?.first, !result.allInstances.isEmpty else {
    FileHandle.standardError.write("nenhum primeiro plano encontrado\n".data(using: .utf8)!)
    exit(3)
}
do {
    // croppedToInstancesExtent: já corta a imagem rente ao recorte (sem margem transparente)
    let buffer = try result.generateMaskedImage(ofInstances: result.allInstances, from: handler, croppedToInstancesExtent: true)
    let ci = CIImage(cvPixelBuffer: buffer)
    let ctx = CIContext()
    let space = CGColorSpace(name: CGColorSpace.sRGB)!
    try ctx.writePNGRepresentation(of: ci, to: outURL, format: .RGBA8, colorSpace: space)
    print("ok \(Int(ci.extent.width))x\(Int(ci.extent.height)) -> \(outURL.path)")
} catch {
    FileHandle.standardError.write("falha ao gerar o recorte: \(error)\n".data(using: .utf8)!)
    exit(1)
}
