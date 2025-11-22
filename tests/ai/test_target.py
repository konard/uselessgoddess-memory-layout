from core.services.ai import Target


def test_scale():
  target = Target(
    input_x=640,
    input_y=640,
    mid_x=320,
    mid_y=320,
    width=160,
    height=160,
    confidence=0.95,
    label="",
    laidx=0,
  )

  assert target == target.scale_to(1, 1).scale_to(640, 640)

  scaled = Target(
    360, 270, 180, 135, 90, 67.5, confidence=0.95, label="", laidx=0
  )
  assert scaled == target.scale_to(360, 270)
