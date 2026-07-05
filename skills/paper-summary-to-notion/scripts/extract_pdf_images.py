#!/usr/bin/env python3
import argparse
import hashlib
import io
from pathlib import Path

import fitz  # PyMuPDF
from PIL import Image


def _flatten_alpha_to_white(image_bytes: bytes, fallback_ext: str) -> tuple[bytes, str]:
    """RGBA/LA/P 팔레트+투명도를 흰 배경 RGB로 평탄화한다."""
    with Image.open(io.BytesIO(image_bytes)) as im:
        if im.mode in ("RGBA", "LA") or (im.mode == "P" and "transparency" in im.info):
            rgba = im.convert("RGBA")
            bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
            merged = Image.alpha_composite(bg, rgba).convert("RGB")
            out = io.BytesIO()
            merged.save(out, format="PNG")
            return out.getvalue(), "png"

        # alpha가 없으면 원본 확장자 유지
        out = io.BytesIO()
        fmt = "PNG" if fallback_ext.lower() == "png" else "JPEG" if fallback_ext.lower() in ("jpg", "jpeg") else "PNG"
        # JPEG 저장 전 RGB 보장
        if fmt == "JPEG":
            im = im.convert("RGB")
        im.save(out, format=fmt)
        return out.getvalue(), fallback_ext.lower() if fallback_ext else "png"


def _passes_min_size(image_bytes: bytes, min_px: int) -> bool:
    with Image.open(io.BytesIO(image_bytes)) as im:
        w, h = im.size
        return max(w, h) >= min_px


def extract_images_from_pdf(pdf_path_str: str, flatten_alpha: bool = True, min_px: int = 300) -> int:
    pdf_path = Path(pdf_path_str)

    # 1) 파일 확인
    if not pdf_path.exists() or not pdf_path.is_file():
        print(f"오류: 파일을 찾을 수 없습니다 -> {pdf_path}")
        return 0

    if pdf_path.suffix.lower() != ".pdf":
        print("오류: PDF 파일만 지원합니다.")
        return 0

    # 2) 저장 폴더 생성 (원본 파일명 기준)
    output_dir = pdf_path.parent / pdf_path.stem
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"폴더 생성 완료: {output_dir}")

    extracted_count = 0

    # 3) PDF 이미지 추출 (논문 내 배치 순서 기준)
    # 순서 정의: page 오름차순 -> 페이지 내 y(top) 오름차순 -> x(left) 오름차순
    try:
        doc = fitz.open(pdf_path)

        seen_img_hashes = set()  # 문서 전체 중복 이미지 제거(동일 바이너리)

        for page_idx in range(len(doc)):
            page = doc[page_idx]

            # 각 xref의 대표 배치 좌표만 사용(페이지 내 첫 등장 위치)
            placement_map = {}
            for img in page.get_images(full=True):
                xref = img[0]
                try:
                    rects = page.get_image_rects(xref)
                except Exception:
                    rects = []

                if not rects:
                    pos = (float('inf'), float('inf'))
                else:
                    pos = min((float(r.y0), float(r.x0)) for r in rects)

                if xref not in placement_map or pos < placement_map[xref]:
                    placement_map[xref] = pos

            # 페이지 내 표시 순서로 정렬
            placements = sorted([(xref, yx[0], yx[1]) for xref, yx in placement_map.items()], key=lambda t: (t[1], t[2], t[0]))

            seq = 0
            for xref, y0, x0 in placements:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                image_ext = base_image.get("ext", "png")

                if flatten_alpha:
                    image_bytes, image_ext = _flatten_alpha_to_white(image_bytes, image_ext)

                if not _passes_min_size(image_bytes, min_px):
                    continue

                # 동일 이미지 바이너리 중복 제거(로고/반복 요소 중복 삽입 방지)
                digest = hashlib.sha1(image_bytes).hexdigest()
                if digest in seen_img_hashes:
                    continue
                seen_img_hashes.add(digest)

                seq += 1
                # 이름 규칙 개선: 페이지/순번을 0-pad로 저장해 정렬 안정화
                image_name = f"page_{page_idx + 1:03d}_img_{seq:03d}.{image_ext}"
                image_filepath = output_dir / image_name

                with open(image_filepath, "wb") as f:
                    f.write(image_bytes)

                extracted_count += 1

        doc.close()
        print(f"작업 완료: 총 {extracted_count}개의 이미지를 성공적으로 추출했습니다.")

    except Exception as e:
        print(f"이미지 추출 중 오류가 발생했습니다: {e}")

    return extracted_count


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PDF 파일에서 이미지를 추출하여 폴더에 저장합니다.")
    parser.add_argument("pdf_path", help="처리할 PDF 파일의 절대 경로나 상대 경로")
    parser.add_argument(
        "--no-flatten-alpha",
        action="store_true",
        help="알파 채널 평탄화(흰 배경 채움) 비활성화",
    )
    parser.add_argument(
        "--min-px",
        type=int,
        default=300,
        help="가로/세로 중 큰 변의 최소 픽셀(기본: 300)",
    )
    args = parser.parse_args()

    extract_images_from_pdf(args.pdf_path, flatten_alpha=not args.no_flatten_alpha, min_px=args.min_px)
