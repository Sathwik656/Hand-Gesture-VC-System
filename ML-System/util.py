import numpy as np

def get_angle(a, b, c):
    # np.arctan2(y, x) is the two-argument arctangent that handles all quadrants correctly.
    # np.arctan(x) is single-argument only and would raise TypeError with two args.
    radians = np.arctan2(c[1] - b[1], c[0] - b[0]) - np.arctan2(a[1] - b[1], a[0] - b[0])
    angle = np.abs(np.degrees(radians))
    return angle

def get_distance(landmark_list):
    if len(landmark_list) < 2:
        return None
    (x1, y1), (x2, y2) = landmark_list[0], landmark_list[1]
    l = np.hypot(x2 - x1, y2 - y1)
    # np.interp(x, xp, fp): map pixel distance l (0–1000 px) to a normalised 0–1 value.
    # [0, 1][0, 1000] was a list indexed with a tuple — a SyntaxWarning/TypeError at runtime.
    return np.interp(l, [0, 1000], [0, 1])