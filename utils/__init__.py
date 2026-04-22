# -*- coding: utf-8 -*-
"""
COURTVIEW - AI 농구 분석 플랫폼

모듈: utils
파일: __init__.py
설명: 유틸리티 모듈 패키지 초기화 - 수학, 기하학, 시간, 영상 처리

작성자: COURTVIEW AI Team
최종 수정: 2026-02-02
버전: 7.0.0

변경 이력:
    - v7.0.0: CV 파이프라인 유틸리티 추가
              camera_calibration_utils (캘리브레이션, 삼각측량, 에피폴라)
              feature_matching_utils (특징점 검출/매칭)
              heatmap_utils (히트맵 피크, 스켈레톤 디코딩)
    - v6.0.0: 농구 기하학 유틸리티 추가 (basketball_geometry)
    - v5.0.0: 고급 통계 분석 모듈 추가 (statistical_utils)
    - v4.0.0: 시퀀스/시계열 분석 모듈 추가 (sequence_utils)
    - v3.0.0: 3D 회전 및 포즈 유틸리티 추가
              rotation_utils, pose_utils
    - v2.0.0: 멀티카메라 3D 분석 지원 모듈 추가
              kalman_utils, physics_utils, interpolation_utils,
              image_utils, validation_utils
    - v1.0.0: 초기 릴리스

Utils 모듈 구성:
    - math_utils: 수학 연산 (각도, 벡터, 통계, 보간)
    - geometry_utils: 기하학 연산 (좌표 변환, 바운딩 박스, 다각형)
    - time_utils: 시간 연산 (프레임↔시간, 타이머, 경기 시간)
    - video_utils: 영상 처리 (프레임 추출, 리사이즈, 코덱)
    - kalman_utils: 칼만 필터 (2D/3D 추적) 🆕 v2.0.0
    - physics_utils: 물리 계산 (궤적, 중력) 🆕 v2.0.0
    - interpolation_utils: 보간 (스플라인, 베지어) 🆕 v2.0.0
    - image_utils: 이미지 처리 (크롭, 리사이즈) 🆕 v2.0.0
    - validation_utils: 입력 검증 🆕 v2.0.0
    - basketball_geometry: 농구 코트/슛 기하학 (7개 리그) 🆕 v6.0.0
    - camera_calibration_utils: 카메라 캘리브레이션/삼각측량 🆕 v7.0.0
    - feature_matching_utils: 특징점 검출/매칭 파이프라인 🆕 v7.0.0
    - heatmap_utils: 히트맵 피크 검출/스켈레톤 디코딩 🆕 v7.0.0
"""
from __future__ import annotations

# =============================================================================
# 수학 유틸리티 (Math Utils)
# =============================================================================
from utils.math_utils import (
    # 타입
    Vector2D,
    Vector3D,
    Point2D,
    Point3D,
    # 상수
    EPSILON,
    DEG_TO_RAD,
    RAD_TO_DEG,
    # 데이터 클래스
    AngleResult,
    StatisticsResult,
    # 각도 변환
    degrees_to_radians,
    radians_to_degrees,
    normalize_angle_degrees,
    normalize_angle_radians,
    angle_difference_degrees,
    # 2D 벡터
    vector2d_magnitude,
    vector2d_normalize,
    vector2d_dot,
    vector2d_cross,
    vector2d_add,
    vector2d_subtract,
    vector2d_scale,
    vector2d_angle,
    vector2d_angle_between,
    vector2d_rotate,
    vector2d_perpendicular,
    vector2d_project,
    # 3D 벡터
    vector3d_magnitude,
    vector3d_normalize,
    vector3d_dot,
    vector3d_cross,
    vector3d_add,
    vector3d_subtract,
    vector3d_scale,
    vector3d_angle_between,
    # 관절 각도
    calculate_joint_angle_2d,
    calculate_joint_angle_3d,
    calculate_flexion_angle,
    calculate_abduction_angle,
    # 통계
    calculate_statistics,
    calculate_weighted_mean,
    calculate_percentile,
    calculate_moving_average,
    calculate_exponential_moving_average,
    # 정규화
    normalize_value,
    clip_value,
    normalize_to_percentage,
    z_score_normalize,
    min_max_normalize,
    # 보간
    lerp,
    lerp_vector2d,
    lerp_vector3d,
    inverse_lerp,
    smooth_step,
    slerp_2d,
    # 거리/유사도
    euclidean_distance_2d,
    euclidean_distance_3d,
    manhattan_distance_2d,
    cosine_similarity,
    # 기타
    safe_divide,
    clamp_angle_degrees,
    is_approximately_equal,
    sign,
    wrap_value,
    # 3D 변환/투영
    rodrigues_to_rotation_matrix,
    rotation_matrix_to_rodrigues,
    apply_homography,
    apply_affine_transform,
    homogeneous_to_cartesian,
    cartesian_to_homogeneous,
    # 회전 변환 (오일러/쿼터니언)
    euler_to_rotation_matrix,
    rotation_matrix_to_euler,
    quaternion_to_rotation_matrix,
    # 행렬 분해 및 선형대수
    svd_decomposition,
    matrix_rank,
    enforce_rank_constraint,
    pseudo_inverse,
    covariance_intersection,
    # NDArray 벡터 연산
    normalize_vector,
    cross_product,
    dot_product,
    weighted_average,
)

# =============================================================================
# 기하학 유틸리티 (Geometry Utils)
# =============================================================================
from utils.geometry_utils import (
    # 타입
    Polygon,
    BBoxFormat,
    # Enum
    BBoxFormatType,
    CourtZone,
    # 데이터 클래스
    BoundingBox,
    CourtDimensions,
    Line2D,
    # 좌표 변환
    normalize_coordinates,
    denormalize_coordinates,
    normalize_keypoints,
    denormalize_keypoints,
    image_to_court_coordinates,
    court_to_image_coordinates,
    compute_homography,
    apply_homography_to_points,
    # 바운딩 박스
    calculate_iou,
    calculate_giou,
    merge_bounding_boxes,
    nms_boxes,
    box_intersection,
    boxes_overlap,
    # 다각형
    polygon_area,
    polygon_centroid,
    point_in_polygon,
    point_in_convex_polygon,
    polygon_bounding_box,
    convex_hull,
    # 거리/투영
    point_to_line_segment_distance,
    point_to_line_distance,
    closest_point_on_line_segment,
    line_segment_intersection,
    # 농구 코트
    determine_court_zone,
    is_three_point_shot,
    calculate_shot_distance,
    # 형상 생성
    create_rectangle,
    create_circle_polygon,
    create_arc_polygon,
    # 배치/고급 기하학
    batch_iou,
    contour_circularity,
    hungarian_match,
)

# =============================================================================
# 시간 유틸리티 (Time Utils)
# =============================================================================
from utils.time_utils import (
    # 상수
    DEFAULT_FPS,
    QUARTER_DURATION_NBA,
    QUARTER_DURATION_FIBA,
    SHOT_CLOCK_NBA,
    SHOT_CLOCK_FIBA,
    OVERTIME_DURATION,
    TIME_FORMAT_HMS,
    TIME_FORMAT_MS,
    TIME_FORMAT_MSM,
    TIME_FORMAT_ISO,
    # Enum
    GamePeriod,
    TimeUnit,
    # 데이터 클래스
    TimeRange,
    FrameRange,
    GameClock,
    TimerResult,
    # 프레임/시간 변환
    frame_to_time,
    time_to_frame,
    frame_to_timecode,
    timecode_to_frame,
    frames_to_duration,
    duration_to_frames,
    # 포맷팅
    format_seconds,
    format_milliseconds,
    format_duration,
    parse_duration,
    # 타임스탬프
    get_current_timestamp,
    get_current_timestamp_ms,
    timestamp_to_datetime,
    datetime_to_timestamp,
    format_timestamp,
    get_iso_timestamp,
    # 성능 측정
    Timer,
    measure_time,
    measure_function,
    # 경기 시간
    get_total_game_time,
    format_game_clock,
    format_shot_clock,
    is_clutch_time,
    # FPS
    calculate_fps,
    calculate_frame_interval,
    calculate_frame_interval_ms,
    should_process_frame,
    get_frame_indices_for_duration,
    iter_frame_indices_for_duration,
    # 단위 변환
    convert_time_unit,
    seconds_to_hms,
    hms_to_seconds,
)

# =============================================================================
# 영상 유틸리티 (Video Utils)
# =============================================================================
from utils.video_utils import (
    # 상수
    SUPPORTED_VIDEO_EXTENSIONS,
    SUPPORTED_IMAGE_EXTENSIONS,
    DEFAULT_CODEC,
    H264_CODEC,
    H265_CODEC,
    BGR_CHANNELS,
    GRAY_CHANNELS,
    RGBA_CHANNELS,
    # Enum
    ColorSpace,
    InterpolationMethod,
    VideoRotation,
    # 데이터 클래스
    VideoMetadata,
    FrameInfo,
    ResizeConfig,
    # 메타데이터
    get_video_metadata,
    is_valid_video_file,
    get_video_resolution,
    get_video_duration,
    get_video_fps,
    # 프레임 추출
    extract_frame,
    extract_frame_at_time,
    extract_frames_range,
    extract_all_frames,
    extract_keyframes,
    # 색상 변환
    convert_color_space,
    # 리사이즈
    resize_image,
    resize_image_maintain_aspect,
    pad_image,
    crop_image,
    rotate_image,
    flip_image,
    # 정규화
    normalize_image,
    denormalize_image,
    to_tensor_format,
    from_tensor_format,
    # 비디오 쓰기
    VideoWriter,
    save_frames_as_video,
    save_frame_as_image,
    # 유틸리티
    get_frame_shape,
    calculate_optimal_batch_size,
    create_thumbnail,
)

# =============================================================================
# 칼만 필터 유틸리티 (Kalman Utils) - v2.0.0
# =============================================================================
from utils.kalman_utils import (
    # Enum
    MotionModel,
    # 데이터 클래스
    KalmanConfig,
    KalmanState,
    KalmanPrediction,
    # 클래스
    KalmanFilter2D,
    KalmanFilter3D,
    ExtendedKalmanFilter,
    # 상수
    DEFAULT_PROCESS_NOISE,
    DEFAULT_MEASUREMENT_NOISE,
    DEFAULT_INITIAL_COVARIANCE,
    # 함수
    create_constant_velocity_model,
    create_constant_acceleration_model,
    compute_mahalanobis_distance,
    compute_innovation,
)

# =============================================================================
# 물리 유틸리티 (Physics Utils) - v2.0.0
# =============================================================================
from utils.physics_utils import (
    # 상수
    GRAVITY,
    BASKETBALL_MASS,
    BASKETBALL_RADIUS,
    BASKETBALL_DRAG_COEFFICIENT,
    AIR_DENSITY,
    # 데이터 클래스
    ProjectileState,
    TrajectoryPoint,
    ImpactResult,
    # 기본 물리
    calculate_gravity_force,
    calculate_drag_force,
    calculate_magnus_force,
    # 발사체 운동
    projectile_motion,
    projectile_motion_with_drag,
    predict_landing_point,
    predict_trajectory,
    # 속도/가속도 추정
    estimate_initial_velocity,
    estimate_velocity_from_trajectory,
    estimate_acceleration,
    # 스핀/회전
    calculate_spin_effect,
    estimate_spin_from_trajectory,
    # 슛 분석
    analyze_shot_trajectory,
    calculate_release_angle,
    calculate_entry_angle,
    predict_shot_result,
)

# =============================================================================
# 보간 유틸리티 (Interpolation Utils) - v2.0.0
# =============================================================================
from utils.interpolation_utils import (
    # Enum
    InterpolationMethod as InterpMethod,  # video_utils의 InterpolationMethod와 구분
    # 데이터 클래스
    InterpolationConfig,
    InterpolatedPoint,
    # 선형 보간
    linear_interpolate,
    linear_interpolate_2d,
    linear_interpolate_3d,
    bilinear_interpolate,
    # 스플라인 보간
    cubic_spline_interpolate,
    spline_interpolate,
    catmull_rom_spline,
    # 베지어 곡선
    bezier_curve,
    bezier_interpolate,
    quadratic_bezier,
    cubic_bezier,
    # 궤적 보간
    interpolate_trajectory,
    resample_trajectory,
    smooth_trajectory,
    # 시간 보간
    interpolate_at_time,
    fill_missing_frames,
    # 유틸리티
    compute_interpolation_weights,
)

# =============================================================================
# 이미지 유틸리티 (Image Utils) - v2.0.0
# =============================================================================
from utils.image_utils import (
    # Enum
    NormalizationMethod,
    # 데이터 클래스
    ImageEnhanceConfig,
    CropRegion,
    # 크롭
    crop_image as image_crop,  # video_utils의 crop_image와 구분
    crop_with_padding,
    crop_center,
    safe_crop,
    # 리사이즈
    resize_image as image_resize,  # video_utils의 resize_image와 구분
    resize_maintain_aspect,
    resize_and_pad,
    letterbox,
    # 이미지 향상
    enhance_contrast,
    enhance_brightness,
    histogram_equalization,
    clahe,
    sharpen_image,
    denoise_image,
    # 정규화
    normalize_image as image_normalize,  # video_utils와 구분
    normalize_imagenet,
    denormalize_image as image_denormalize,  # video_utils와 구분
    standardize_image,
    # 색상 변환
    bgr_to_rgb,
    rgb_to_bgr,
    to_grayscale,
    to_hsv,
    # 텐서 변환
    to_tensor,
    from_tensor,
    # 유틸리티
    compute_image_hash,
    compute_ssim,
    blend_images,
    # 고급 이미지 분석
    compute_phash,
    motion_blur_score,
)

# =============================================================================
# 검증 유틸리티 (Validation Utils) - v2.0.0
# =============================================================================
from utils.validation_utils import (
    # 타입 변수
    T,
    # 널/빈 값 검증
    validate_not_none,
    validate_not_empty,
    validate_not_blank,
    # 숫자 범위 검증
    validate_positive,
    validate_non_negative,
    validate_range,
    validate_percentage,
    validate_probability,
    # 타입 검증
    validate_type,
    validate_instance,
    validate_callable,
    # 시퀀스 검증
    validate_length,
    validate_all_positive,
    validate_unique,
    # 도메인 검증 (농구)
    validate_jersey_number,
    validate_court_position,
    validate_player_count,
    validate_camera_count,
    # 조건부 검증
    validate_if,
    validate_one_of,
    validate_all,
    validate_any,
    # 래퍼/데코레이터
    validated,
    require_positive,
    require_non_empty,
    # 3D 기하학 검증
    validate_rotation_matrix,
    validate_quaternion,
)

# =============================================================================
# 회전 유틸리티 (Rotation Utils) - v3.0.0
# =============================================================================
from utils.rotation_utils import (
    # 상수
    GIMBAL_LOCK_THRESHOLD,
    QUATERNION_NORM_TOLERANCE,
    ORTHOGONALITY_TOLERANCE,
    DETERMINANT_TOLERANCE,
    # Enum
    RotationOrder,
    RotationFormat,
    # 데이터 클래스
    AxisAngle,
    Quaternion,
    AngularVelocity,
    RotationDistance,
    # 축-각도 변환
    axis_angle_to_rotation_matrix,
    rotation_matrix_to_axis_angle,
    axis_angle_to_quaternion,
    axis_angle_to_rodrigues,
    # 쿼터니언 대수
    quaternion_normalize,
    quaternion_conjugate,
    quaternion_inverse,
    quaternion_multiply,
    quaternion_rotate_point,
    quaternion_slerp,
    # 쿼터니언 변환
    quaternion_to_axis_angle,
    quaternion_to_euler,
    quaternion_to_matrix,
    quaternion_to_rodrigues,
    # 회전행렬 변환
    rotation_matrix_to_quaternion,
    # 로드리게스 변환
    rodrigues_to_axis_angle,
    rodrigues_to_quaternion,
    # 오일러 변환
    euler_to_quaternion,
    # 회전 합성/보간
    compose_rotations,
    relative_rotation,
    rotation_matrix_slerp,
    # SO(3) 검증/정규화
    is_valid_rotation_matrix,
    normalize_rotation_matrix,
    is_near_gimbal_lock,
    # 거리 메트릭
    rotation_distance,
    rotation_error,
    # 각속도
    angular_velocity_from_matrices,
    angular_velocity_from_quaternions,
    # 배치 연산
    batch_axis_angle_to_matrices,
    batch_rodrigues_to_matrices,
    batch_matrices_to_rodrigues,
    batch_transform_points,
    # 좌표 프레임
    skew_symmetric,
    rotation_matrix_to_homogeneous,
    homogeneous_to_rotation,
)

# =============================================================================
# 포즈/스켈레톤 유틸리티 (Pose Utils) - v3.0.0
# =============================================================================
from utils.pose_utils import (
    # 상수
    DEFAULT_CONFIDENCE_THRESHOLD as POSE_CONFIDENCE_THRESHOLD,
    HIGH_CONFIDENCE_THRESHOLD as POSE_HIGH_CONFIDENCE,
    COCO_NUM_KEYPOINTS,
    OKS_SIGMAS,
    SKELETON_CONNECTIONS,
    KP_NOSE, KP_LEFT_EYE, KP_RIGHT_EYE,
    KP_LEFT_EAR, KP_RIGHT_EAR,
    KP_LEFT_SHOULDER, KP_RIGHT_SHOULDER,
    KP_LEFT_ELBOW, KP_RIGHT_ELBOW,
    KP_LEFT_WRIST, KP_RIGHT_WRIST,
    KP_LEFT_HIP, KP_RIGHT_HIP,
    KP_LEFT_KNEE, KP_RIGHT_KNEE,
    KP_LEFT_ANKLE, KP_RIGHT_ANKLE,
    # 운동학 체인
    KINEMATIC_PARENT_MAP,
    KINEMATIC_CHILDREN_MAP,
    BODY_PART_KEYPOINTS,
    KEYPOINT_TO_BODY_PART,
    # Enum
    NormalizationMethod as PoseNormMethod,
    SmoothingMethod as PoseSmoothMethod,
    BodyPart,
    # 데이터 클래스
    SkeletonMetrics,
    ProcrustesResult,
    MotionSmoothness,
    BodyOrientation,
    # 변환
    skeleton_to_numpy,
    skeleton_to_numpy_3d,
    numpy_to_keypoints,
    # 메트릭
    calculate_skeleton_metrics,
    # 정규화
    normalize_skeleton_scale,
    # 필터링/보간
    filter_keypoints_by_confidence,
    interpolate_missing_keypoints,
    mirror_skeleton,
    # 팔다리/운동학
    get_limb_vector,
    calculate_limb_length,
    calculate_all_limb_lengths,
    get_body_part_center,
    estimate_center_of_mass,
    # 속도/가속도/저크
    calculate_keypoint_velocities,
    calculate_keypoint_accelerations,
    calculate_jerk,
    calculate_keypoint_speed,
    # 포즈 비교
    oks_similarity,
    procrustes_align,
    pose_distance,
    # 신체 방향
    estimate_body_orientation,
    estimate_facing_direction,
    # 시계열
    extract_temporal_window,
    calculate_motion_smoothness,
    smooth_keypoint_sequence,
    detect_keyframe_indices,
    calculate_temporal_consistency,
)

# =============================================================================
# 시퀀스/시계열 유틸리티 (Sequence Utils) - v4.0.0
# =============================================================================
from utils.sequence_utils import (
    # 상수
    MAX_DTW_SEQUENCE_LENGTH,
    DEFAULT_MIN_PHASE_LENGTH,
    DEFAULT_PEAK_MIN_DISTANCE,
    DEFAULT_PEAK_MIN_PROMINENCE,
    DEFAULT_WINDOW_SIZE,
    DEFAULT_WINDOW_STRIDE,
    # Enum
    PaddingMode,
    DistanceMetric,
    SegmentationMethod,
    # 데이터 클래스
    DTWResult,
    PhaseSegment,
    PeakInfo,
    SequenceAlignment,
    PeriodicityResult,
    # 시퀀스 정규화
    z_normalize_sequence,
    min_max_normalize_sequence,
    resample_sequence,
    pad_or_truncate,
    standardize_lengths,
    # 시퀀스 비교/거리
    dtw_distance,
    frechet_distance,
    sequence_cosine_similarity,
    sequence_pearson_correlation,
    sequence_euclidean_distance,
    # 위상 분할
    detect_phase_transitions,
    segment_by_velocity,
    segment_by_curvature,
    find_zero_crossings,
    # 슬라이딩 윈도우
    sliding_window,
    sliding_window_statistics,
    extract_subsequences,
    # 피크 검출
    find_peaks,
    find_valleys,
    # 주기성/상관
    compute_autocorrelation,
    compute_cross_correlation,
    detect_periodicity,
    calculate_sequence_entropy,
    # 정렬/워핑
    align_sequences_dtw,
    warp_sequence,
    template_match,
    # 배치 연산
    batch_dtw_distances,
    batch_normalize_sequences,
)

# =============================================================================
# 통계 유틸리티 (Statistical Utils) - v5.0.0
# =============================================================================
from utils.statistical_utils import (
    # 상수
    DEFAULT_CONFIDENCE_LEVEL,
    Z_CRITICAL_95,
    Z_CRITICAL_99,
    DEFAULT_OUTLIER_THRESHOLD,
    DEFAULT_IQR_MULTIPLIER,
    # Enum
    OutlierMethod,
    RankMethod,
    # 데이터 클래스
    DistributionStats,
    ConfidenceInterval,
    OutlierResult,
    RankingResult,
    ICCResult,
    # 클래스
    RunningStatistics,
    # 분포 분석
    calculate_distribution_stats,
    calculate_skewness,
    calculate_kurtosis,
    z_to_percentile,
    percentile_to_z,
    # 변동/일관성
    coefficient_of_variation,
    consistency_score,
    temporal_consistency_index,
    # 이상값 검출
    detect_outliers_zscore,
    detect_outliers_iqr,
    detect_outliers_mad,
    filter_outliers,
    # 가중 집계
    weighted_score,
    normalize_weights,
    trimmed_mean,
    bayesian_average,
    harmonic_mean,
    # 순위/백분위
    percentile_rank,
    rank_values,
    standardize_scores,
    # 신뢰구간
    confidence_interval_z,
    margin_of_error,
    # 신뢰도 메트릭
    icc_two_way,
    cronbach_alpha,
    cohens_d,
    # 러닝/온라인 통계
    running_variance,
    exponential_decay_average,
    # 배치 연산
    batch_distribution_stats,
)

# =============================================================================
# 농구 기하학 유틸리티 (Basketball Geometry) - v6.0.0
# =============================================================================
from utils.basketball_geometry import (
    # 상수 (GRAVITY는 physics_utils와 동일값 — 생략)
    HOOP_HEIGHT_M,
    HOOP_DIAMETER_M,
    HOOP_RADIUS_M,
    BALL_DIAMETER_M,
    BALL_RADIUS_M,
    BACKBOARD_WIDTH_M,
    BACKBOARD_HEIGHT_M,
    BACKBOARD_OFFSET_FROM_ENDLINE_M,
    HOOP_OFFSET_FROM_BACKBOARD_M,
    OPTIMAL_RELEASE_ANGLE_MIN,
    OPTIMAL_RELEASE_ANGLE_MAX,
    OPTIMAL_ENTRY_ANGLE_MIN,
    OPTIMAL_ENTRY_ANGLE_MAX,
    # Enum
    CourtStandard,
    ShotRegion,
    HoopSide,
    # 데이터 클래스
    CourtSpec,
    HoopPosition3D,
    ShotGeometry,
    TrajectoryGeometry,
    RimClearance,
    # 코트 규격
    get_court_spec,
    get_three_point_distance,
    # 3D 림/백보드 위치
    get_hoop_position_2d,
    get_hoop_position_3d,
    get_backboard_position_3d,
    # 슛 위치 분석
    distance_to_hoop,
    angle_from_hoop,
    classify_shot_region,
    is_three_point,
    is_corner_position,
    is_in_paint,
    get_point_value,
    analyze_shot_location,
    # 슛 궤적 기하학 (physics_utils 충돌 → 별칭)
    optimal_release_angle,
    required_velocity,
    calculate_entry_angle as bg_entry_angle,  # physics_utils의 calculate_entry_angle과 구분
    calculate_arc_height,
    calculate_apex_position,
    calculate_flight_time,
    analyze_shot_trajectory as bg_analyze_trajectory,  # physics_utils의 analyze_shot_trajectory과 구분
    # 림 통과 기하학
    effective_rim_diameter,
    rim_clearance,
    minimum_entry_angle,
    is_bank_shot_viable,
    # 코트 좌표 변환
    normalize_to_half_court,
    denormalize_from_half_court,
    mirror_court_position,
    # 3D 유틸리티
    is_above_rim,
    is_in_cylinder,
    # 배치 연산
    batch_distance_to_hoop,
    batch_classify_shot_regions,
    batch_analyze_shot_locations,
)

# =============================================================================
# 카메라 캘리브레이션 유틸리티 (Camera Calibration Utils) v7.0.0
# =============================================================================
from utils.camera_calibration_utils import (
    # 상수
    DEFAULT_RANSAC_THRESHOLD,
    DEFAULT_RANSAC_CONFIDENCE,
    DEFAULT_RANSAC_MAX_ITERS,
    REPROJECTION_ERROR_THRESHOLD,
    MIN_POINTS_FUNDAMENTAL,
    MIN_POINTS_ESSENTIAL,
    MIN_PARALLAX_DEGREES,
    # Enum
    DistortionModel,
    FundamentalMethod,
    TriangulationMethod,
    # 데이터 클래스
    CameraIntrinsics,
    DistortionCoeffs,
    CameraExtrinsics,
    FundamentalResult,
    EssentialDecomposition,
    TriangulationResult,
    ReprojectionError,
    # 내부 파라미터
    build_intrinsic_matrix,
    decompose_intrinsic_matrix,
    validate_intrinsic_matrix,
    # 왜곡 보정
    undistort_points,
    undistort_image,
    distort_points,
    # 기본 행렬 / 본질 행렬
    compute_fundamental_matrix,
    compute_essential_matrix,
    decompose_essential_matrix,
    # 에피폴라 기하학
    compute_epipole,
    compute_epipolar_line,
    point_to_epipolar_distance,
    # 삼각측량
    triangulate_points_dlt,
    triangulate_points_midpoint,
    triangulate_points,
    # 리프로젝션 오차
    compute_reprojection_errors,
    compute_reprojection_stats,
    # 투영 행렬
    build_projection_matrix,
    decompose_projection_matrix,
    # 좌표 변환
    pixel_to_normalized,
    normalized_to_pixel,
    world_to_pixel,
    pixel_to_ray,
    # 배치 연산
    batch_undistort_points,
    batch_project_points,
    # 카메라 시야각 / 깊이
    compute_field_of_view,
    compute_focal_from_fov,
    estimate_depth_accuracy,
)

# =============================================================================
# 특징점 매칭 유틸리티 (Feature Matching Utils) v7.0.0
# =============================================================================
from utils.feature_matching_utils import (
    # 상수
    DEFAULT_RATIO_THRESHOLD,
    DEFAULT_CROSS_CHECK,
    DEFAULT_ORB_FEATURES,
    DEFAULT_SIFT_FEATURES,
    DEFAULT_AKAZE_THRESHOLD,
    DEFAULT_BRISK_THRESHOLD,
    DEFAULT_HOMOGRAPHY_THRESHOLD,
    DEFAULT_EPIPOLAR_THRESHOLD,
    MIN_GOOD_MATCHES,
    # Enum
    DetectorType,
    MatcherType,
    DescriptorNorm,
    # 데이터 클래스
    KeypointInfo,
    DetectionResult,
    MatchPair,
    MatchResult,
    MatchQuality,
    # 특징점 검출
    detect_keypoints,
    detect_keypoints_multiscale,
    # 디스크립터 매칭
    match_descriptors,
    filter_matches_ratio,
    filter_matches_symmetric,
    # 기하학적 필터링
    filter_matches_homography,
    filter_matches_epipolar,
    filter_matches_distance,
    # 통합 파이프라인
    match_images,
    # 품질 분석
    compute_match_quality,
    compute_descriptor_distance,
    compute_descriptor_distance_matrix,
    # 유틸리티
    extract_matched_points,
    spatial_consistency_filter,
)

# =============================================================================
# 히트맵 유틸리티 (Heatmap Utils) v7.0.0
# =============================================================================
from utils.heatmap_utils import (
    # 상수
    DEFAULT_PEAK_THRESHOLD,
    DEFAULT_GAUSSIAN_SIGMA,
    DEFAULT_NMS_KERNEL_SIZE,
    COCO_KEYPOINT_NAMES,
    COCO_SKELETON_CONNECTIONS,
    # Enum
    SubpixelMethod,
    HeatmapAggregation,
    # 데이터 클래스
    HeatmapConfig,
    PeakInfo as HeatmapPeakInfo,  # sequence_utils.PeakInfo와 구분
    SkeletonResult,
    HeatmapQuality,
    # 피크 검출
    extract_peaks,
    extract_peaks_batch,
    extract_top_peak,
    # 가우시안 히트맵 생성
    generate_gaussian_heatmap,
    generate_multi_keypoint_heatmap,
    # 스켈레톤 디코딩
    decode_heatmaps_to_skeleton,
    decode_multi_person_heatmaps,
    # 히트맵 앙상블
    aggregate_heatmaps,
    flip_heatmap_horizontal,
    # 품질 분석
    compute_heatmap_quality,
    # 리사이즈/변환
    resize_heatmap,
    normalize_heatmap,
)

__all__ = [
    # =========================================================================
    # 수학 유틸리티
    # =========================================================================
    # 타입
    "Vector2D",
    "Vector3D",
    "Point2D",
    "Point3D",
    # 상수
    "EPSILON",
    "DEG_TO_RAD",
    "RAD_TO_DEG",
    # 데이터 클래스
    "AngleResult",
    "StatisticsResult",
    # 각도 변환
    "degrees_to_radians",
    "radians_to_degrees",
    "normalize_angle_degrees",
    "normalize_angle_radians",
    "angle_difference_degrees",
    # 2D 벡터
    "vector2d_magnitude",
    "vector2d_normalize",
    "vector2d_dot",
    "vector2d_cross",
    "vector2d_add",
    "vector2d_subtract",
    "vector2d_scale",
    "vector2d_angle",
    "vector2d_angle_between",
    "vector2d_rotate",
    "vector2d_perpendicular",
    "vector2d_project",
    # 3D 벡터
    "vector3d_magnitude",
    "vector3d_normalize",
    "vector3d_dot",
    "vector3d_cross",
    "vector3d_add",
    "vector3d_subtract",
    "vector3d_scale",
    "vector3d_angle_between",
    # 관절 각도
    "calculate_joint_angle_2d",
    "calculate_joint_angle_3d",
    "calculate_flexion_angle",
    "calculate_abduction_angle",
    # 통계
    "calculate_statistics",
    "calculate_weighted_mean",
    "calculate_percentile",
    "calculate_moving_average",
    "calculate_exponential_moving_average",
    # 정규화
    "normalize_value",
    "clip_value",
    "normalize_to_percentage",
    "z_score_normalize",
    "min_max_normalize",
    # 보간
    "lerp",
    "lerp_vector2d",
    "lerp_vector3d",
    "inverse_lerp",
    "smooth_step",
    "slerp_2d",
    # 거리/유사도
    "euclidean_distance_2d",
    "euclidean_distance_3d",
    "manhattan_distance_2d",
    "cosine_similarity",
    # 기타
    "safe_divide",
    "clamp_angle_degrees",
    "is_approximately_equal",
    "sign",
    "wrap_value",
    # 3D 변환/투영
    "rodrigues_to_rotation_matrix",
    "rotation_matrix_to_rodrigues",
    "apply_homography",
    "apply_affine_transform",
    "homogeneous_to_cartesian",
    "cartesian_to_homogeneous",
    # 회전 변환 (오일러/쿼터니언)
    "euler_to_rotation_matrix",
    "rotation_matrix_to_euler",
    "quaternion_to_rotation_matrix",
    # 행렬 분해 및 선형대수
    "svd_decomposition",
    "matrix_rank",
    "enforce_rank_constraint",
    "pseudo_inverse",
    "covariance_intersection",
    # NDArray 벡터 연산
    "normalize_vector",
    "cross_product",
    "dot_product",
    "weighted_average",
    # =========================================================================
    # 기하학 유틸리티
    # =========================================================================
    # 타입
    "Polygon",
    "BBoxFormat",
    # Enum
    "BBoxFormatType",
    "CourtZone",
    # 데이터 클래스
    "BoundingBox",
    "CourtDimensions",
    "Line2D",
    # 좌표 변환
    "normalize_coordinates",
    "denormalize_coordinates",
    "normalize_keypoints",
    "denormalize_keypoints",
    "image_to_court_coordinates",
    "court_to_image_coordinates",
    "compute_homography",
    "apply_homography_to_points",
    # 바운딩 박스
    "calculate_iou",
    "calculate_giou",
    "merge_bounding_boxes",
    "nms_boxes",
    "box_intersection",
    "boxes_overlap",
    # 다각형
    "polygon_area",
    "polygon_centroid",
    "point_in_polygon",
    "point_in_convex_polygon",
    "polygon_bounding_box",
    "convex_hull",
    # 거리/투영
    "point_to_line_segment_distance",
    "point_to_line_distance",
    "closest_point_on_line_segment",
    "line_segment_intersection",
    # 농구 코트
    "determine_court_zone",
    "is_three_point_shot",
    "calculate_shot_distance",
    # 형상 생성
    "create_rectangle",
    "create_circle_polygon",
    "create_arc_polygon",
    # 배치/고급 기하학
    "batch_iou",
    "contour_circularity",
    "hungarian_match",
    # =========================================================================
    # 시간 유틸리티
    # =========================================================================
    # 상수
    "DEFAULT_FPS",
    "QUARTER_DURATION_NBA",
    "QUARTER_DURATION_FIBA",
    "SHOT_CLOCK_NBA",
    "SHOT_CLOCK_FIBA",
    "OVERTIME_DURATION",
    "TIME_FORMAT_HMS",
    "TIME_FORMAT_MS",
    "TIME_FORMAT_MSM",
    "TIME_FORMAT_ISO",
    # Enum
    "GamePeriod",
    "TimeUnit",
    # 데이터 클래스
    "TimeRange",
    "FrameRange",
    "GameClock",
    "TimerResult",
    # 프레임/시간 변환
    "frame_to_time",
    "time_to_frame",
    "frame_to_timecode",
    "timecode_to_frame",
    "frames_to_duration",
    "duration_to_frames",
    # 포맷팅
    "format_seconds",
    "format_milliseconds",
    "format_duration",
    "parse_duration",
    # 타임스탬프
    "get_current_timestamp",
    "get_current_timestamp_ms",
    "timestamp_to_datetime",
    "datetime_to_timestamp",
    "format_timestamp",
    "get_iso_timestamp",
    # 성능 측정
    "Timer",
    "measure_time",
    "measure_function",
    # 경기 시간
    "get_total_game_time",
    "format_game_clock",
    "format_shot_clock",
    "is_clutch_time",
    # FPS
    "calculate_fps",
    "calculate_frame_interval",
    "calculate_frame_interval_ms",
    "should_process_frame",
    "get_frame_indices_for_duration",
    "iter_frame_indices_for_duration",
    # 단위 변환
    "convert_time_unit",
    "seconds_to_hms",
    "hms_to_seconds",
    # =========================================================================
    # 영상 유틸리티
    # =========================================================================
    # 상수
    "SUPPORTED_VIDEO_EXTENSIONS",
    "SUPPORTED_IMAGE_EXTENSIONS",
    "DEFAULT_CODEC",
    "H264_CODEC",
    "H265_CODEC",
    "BGR_CHANNELS",
    "GRAY_CHANNELS",
    "RGBA_CHANNELS",
    # Enum
    "ColorSpace",
    "InterpolationMethod",
    "VideoRotation",
    # 데이터 클래스
    "VideoMetadata",
    "FrameInfo",
    "ResizeConfig",
    # 메타데이터
    "get_video_metadata",
    "is_valid_video_file",
    "get_video_resolution",
    "get_video_duration",
    "get_video_fps",
    # 프레임 추출
    "extract_frame",
    "extract_frame_at_time",
    "extract_frames_range",
    "extract_all_frames",
    "extract_keyframes",
    # 색상 변환
    "convert_color_space",
    # 리사이즈
    "resize_image",
    "resize_image_maintain_aspect",
    "pad_image",
    "crop_image",
    "rotate_image",
    "flip_image",
    # 정규화
    "normalize_image",
    "denormalize_image",
    "to_tensor_format",
    "from_tensor_format",
    # 비디오 쓰기
    "VideoWriter",
    "save_frames_as_video",
    "save_frame_as_image",
    # 유틸리티
    "get_frame_shape",
    "calculate_optimal_batch_size",
    "create_thumbnail",
    # =========================================================================
    # 칼만 필터 유틸리티 (v2.0.0)
    # =========================================================================
    "MotionModel",
    "KalmanConfig",
    "KalmanState",
    "KalmanPrediction",
    "KalmanFilter2D",
    "KalmanFilter3D",
    "ExtendedKalmanFilter",
    "DEFAULT_PROCESS_NOISE",
    "DEFAULT_MEASUREMENT_NOISE",
    "DEFAULT_INITIAL_COVARIANCE",
    "create_constant_velocity_model",
    "create_constant_acceleration_model",
    "compute_mahalanobis_distance",
    "compute_innovation",
    # =========================================================================
    # 물리 유틸리티 (v2.0.0)
    # =========================================================================
    "GRAVITY",
    "BASKETBALL_MASS",
    "BASKETBALL_RADIUS",
    "BASKETBALL_DRAG_COEFFICIENT",
    "AIR_DENSITY",
    "ProjectileState",
    "TrajectoryPoint",
    "ImpactResult",
    "calculate_gravity_force",
    "calculate_drag_force",
    "calculate_magnus_force",
    "projectile_motion",
    "projectile_motion_with_drag",
    "predict_landing_point",
    "predict_trajectory",
    "estimate_initial_velocity",
    "estimate_velocity_from_trajectory",
    "estimate_acceleration",
    "calculate_spin_effect",
    "estimate_spin_from_trajectory",
    "analyze_shot_trajectory",
    "calculate_release_angle",
    "calculate_entry_angle",
    "predict_shot_result",
    # =========================================================================
    # 보간 유틸리티 (v2.0.0)
    # =========================================================================
    "InterpMethod",
    "InterpolationConfig",
    "InterpolatedPoint",
    "linear_interpolate",
    "linear_interpolate_2d",
    "linear_interpolate_3d",
    "bilinear_interpolate",
    "cubic_spline_interpolate",
    "spline_interpolate",
    "catmull_rom_spline",
    "bezier_curve",
    "bezier_interpolate",
    "quadratic_bezier",
    "cubic_bezier",
    "interpolate_trajectory",
    "resample_trajectory",
    "smooth_trajectory",
    "interpolate_at_time",
    "fill_missing_frames",
    "compute_interpolation_weights",
    # =========================================================================
    # 이미지 유틸리티 (v2.0.0)
    # =========================================================================
    "NormalizationMethod",
    "ImageEnhanceConfig",
    "CropRegion",
    "image_crop",
    "crop_with_padding",
    "crop_center",
    "safe_crop",
    "image_resize",
    "resize_maintain_aspect",
    "resize_and_pad",
    "letterbox",
    "enhance_contrast",
    "enhance_brightness",
    "histogram_equalization",
    "clahe",
    "sharpen_image",
    "denoise_image",
    "image_normalize",
    "normalize_imagenet",
    "image_denormalize",
    "standardize_image",
    "bgr_to_rgb",
    "rgb_to_bgr",
    "to_grayscale",
    "to_hsv",
    "to_tensor",
    "from_tensor",
    "compute_image_hash",
    "compute_ssim",
    "blend_images",
    # 고급 이미지 분석
    "compute_phash",
    "motion_blur_score",
    # =========================================================================
    # 검증 유틸리티 (v2.0.0)
    # =========================================================================
    "T",
    "validate_not_none",
    "validate_not_empty",
    "validate_not_blank",
    "validate_positive",
    "validate_non_negative",
    "validate_range",
    "validate_percentage",
    "validate_probability",
    "validate_type",
    "validate_instance",
    "validate_callable",
    "validate_length",
    "validate_all_positive",
    "validate_unique",
    "validate_jersey_number",
    "validate_court_position",
    "validate_player_count",
    "validate_camera_count",
    "validate_if",
    "validate_one_of",
    "validate_all",
    "validate_any",
    "validated",
    "require_positive",
    "require_non_empty",
    # 3D 기하학 검증
    "validate_rotation_matrix",
    "validate_quaternion",
    # =========================================================================
    # 회전 유틸리티 (v3.0.0)
    # =========================================================================
    # 상수
    "GIMBAL_LOCK_THRESHOLD",
    "QUATERNION_NORM_TOLERANCE",
    "ORTHOGONALITY_TOLERANCE",
    "DETERMINANT_TOLERANCE",
    # Enum
    "RotationOrder",
    "RotationFormat",
    # 데이터 클래스
    "AxisAngle",
    "Quaternion",
    "AngularVelocity",
    "RotationDistance",
    # 축-각도 변환
    "axis_angle_to_rotation_matrix",
    "rotation_matrix_to_axis_angle",
    "axis_angle_to_quaternion",
    "axis_angle_to_rodrigues",
    # 쿼터니언 대수
    "quaternion_normalize",
    "quaternion_conjugate",
    "quaternion_inverse",
    "quaternion_multiply",
    "quaternion_rotate_point",
    "quaternion_slerp",
    # 쿼터니언 변환
    "quaternion_to_axis_angle",
    "quaternion_to_euler",
    "quaternion_to_matrix",
    "quaternion_to_rodrigues",
    # 회전행렬 변환
    "rotation_matrix_to_quaternion",
    # 로드리게스 변환
    "rodrigues_to_axis_angle",
    "rodrigues_to_quaternion",
    # 오일러 변환
    "euler_to_quaternion",
    # 회전 합성/보간
    "compose_rotations",
    "relative_rotation",
    "rotation_matrix_slerp",
    # SO(3) 검증/정규화
    "is_valid_rotation_matrix",
    "normalize_rotation_matrix",
    "is_near_gimbal_lock",
    # 거리 메트릭
    "rotation_distance",
    "rotation_error",
    # 각속도
    "angular_velocity_from_matrices",
    "angular_velocity_from_quaternions",
    # 배치 연산
    "batch_axis_angle_to_matrices",
    "batch_rodrigues_to_matrices",
    "batch_matrices_to_rodrigues",
    "batch_transform_points",
    # 좌표 프레임
    "skew_symmetric",
    "rotation_matrix_to_homogeneous",
    "homogeneous_to_rotation",
    # =========================================================================
    # 포즈/스켈레톤 유틸리티 (v3.0.0)
    # =========================================================================
    # 상수
    "POSE_CONFIDENCE_THRESHOLD",
    "POSE_HIGH_CONFIDENCE",
    "COCO_NUM_KEYPOINTS",
    "OKS_SIGMAS",
    "SKELETON_CONNECTIONS",
    # 키포인트 인덱스
    "KP_NOSE", "KP_LEFT_EYE", "KP_RIGHT_EYE",
    "KP_LEFT_EAR", "KP_RIGHT_EAR",
    "KP_LEFT_SHOULDER", "KP_RIGHT_SHOULDER",
    "KP_LEFT_ELBOW", "KP_RIGHT_ELBOW",
    "KP_LEFT_WRIST", "KP_RIGHT_WRIST",
    "KP_LEFT_HIP", "KP_RIGHT_HIP",
    "KP_LEFT_KNEE", "KP_RIGHT_KNEE",
    "KP_LEFT_ANKLE", "KP_RIGHT_ANKLE",
    # 운동학 체인
    "KINEMATIC_PARENT_MAP",
    "KINEMATIC_CHILDREN_MAP",
    "BODY_PART_KEYPOINTS",
    "KEYPOINT_TO_BODY_PART",
    # Enum
    "PoseNormMethod",
    "PoseSmoothMethod",
    "BodyPart",
    # 데이터 클래스
    "SkeletonMetrics",
    "ProcrustesResult",
    "MotionSmoothness",
    "BodyOrientation",
    # 변환
    "skeleton_to_numpy",
    "skeleton_to_numpy_3d",
    "numpy_to_keypoints",
    # 메트릭
    "calculate_skeleton_metrics",
    # 정규화
    "normalize_skeleton_scale",
    # 필터링/보간
    "filter_keypoints_by_confidence",
    "interpolate_missing_keypoints",
    "mirror_skeleton",
    # 팔다리/운동학
    "get_limb_vector",
    "calculate_limb_length",
    "calculate_all_limb_lengths",
    "get_body_part_center",
    "estimate_center_of_mass",
    # 속도/가속도/저크
    "calculate_keypoint_velocities",
    "calculate_keypoint_accelerations",
    "calculate_jerk",
    "calculate_keypoint_speed",
    # 포즈 비교
    "oks_similarity",
    "procrustes_align",
    "pose_distance",
    # 신체 방향
    "estimate_body_orientation",
    "estimate_facing_direction",
    # 시계열
    "extract_temporal_window",
    "calculate_motion_smoothness",
    "smooth_keypoint_sequence",
    "detect_keyframe_indices",
    "calculate_temporal_consistency",
    # =========================================================================
    # 시퀀스/시계열 유틸리티 (v4.0.0)
    # =========================================================================
    # 상수
    "MAX_DTW_SEQUENCE_LENGTH",
    "DEFAULT_MIN_PHASE_LENGTH",
    "DEFAULT_PEAK_MIN_DISTANCE",
    "DEFAULT_PEAK_MIN_PROMINENCE",
    "DEFAULT_WINDOW_SIZE",
    "DEFAULT_WINDOW_STRIDE",
    # Enum
    "PaddingMode",
    "DistanceMetric",
    "SegmentationMethod",
    # 데이터 클래스
    "DTWResult",
    "PhaseSegment",
    "PeakInfo",
    "SequenceAlignment",
    "PeriodicityResult",
    # 시퀀스 정규화
    "z_normalize_sequence",
    "min_max_normalize_sequence",
    "resample_sequence",
    "pad_or_truncate",
    "standardize_lengths",
    # 시퀀스 비교/거리
    "dtw_distance",
    "frechet_distance",
    "sequence_cosine_similarity",
    "sequence_pearson_correlation",
    "sequence_euclidean_distance",
    # 위상 분할
    "detect_phase_transitions",
    "segment_by_velocity",
    "segment_by_curvature",
    "find_zero_crossings",
    # 슬라이딩 윈도우
    "sliding_window",
    "sliding_window_statistics",
    "extract_subsequences",
    # 피크 검출
    "find_peaks",
    "find_valleys",
    # 주기성/상관
    "compute_autocorrelation",
    "compute_cross_correlation",
    "detect_periodicity",
    "calculate_sequence_entropy",
    # 정렬/워핑
    "align_sequences_dtw",
    "warp_sequence",
    "template_match",
    # 배치 연산
    "batch_dtw_distances",
    "batch_normalize_sequences",
    # =========================================================================
    # 통계 유틸리티 (v5.0.0)
    # =========================================================================
    # 상수
    "DEFAULT_CONFIDENCE_LEVEL",
    "Z_CRITICAL_95",
    "Z_CRITICAL_99",
    "DEFAULT_OUTLIER_THRESHOLD",
    "DEFAULT_IQR_MULTIPLIER",
    # Enum
    "OutlierMethod",
    "RankMethod",
    # 데이터 클래스
    "DistributionStats",
    "ConfidenceInterval",
    "OutlierResult",
    "RankingResult",
    "ICCResult",
    # 클래스
    "RunningStatistics",
    # 분포 분석
    "calculate_distribution_stats",
    "calculate_skewness",
    "calculate_kurtosis",
    "z_to_percentile",
    "percentile_to_z",
    # 변동/일관성
    "coefficient_of_variation",
    "consistency_score",
    "temporal_consistency_index",
    # 이상값 검출
    "detect_outliers_zscore",
    "detect_outliers_iqr",
    "detect_outliers_mad",
    "filter_outliers",
    # 가중 집계
    "weighted_score",
    "normalize_weights",
    "trimmed_mean",
    "bayesian_average",
    "harmonic_mean",
    # 순위/백분위
    "percentile_rank",
    "rank_values",
    "standardize_scores",
    # 신뢰구간
    "confidence_interval_z",
    "margin_of_error",
    # 신뢰도 메트릭
    "icc_two_way",
    "cronbach_alpha",
    "cohens_d",
    # 러닝/온라인 통계
    "running_variance",
    "exponential_decay_average",
    # 배치 연산
    "batch_distribution_stats",
    # =========================================================================
    # 농구 기하학 유틸리티 (v6.0.0)
    # =========================================================================
    # 상수
    "HOOP_HEIGHT_M",
    "HOOP_DIAMETER_M",
    "HOOP_RADIUS_M",
    "BALL_DIAMETER_M",
    "BALL_RADIUS_M",
    "BACKBOARD_WIDTH_M",
    "BACKBOARD_HEIGHT_M",
    "BACKBOARD_OFFSET_FROM_ENDLINE_M",
    "HOOP_OFFSET_FROM_BACKBOARD_M",
    "OPTIMAL_RELEASE_ANGLE_MIN",
    "OPTIMAL_RELEASE_ANGLE_MAX",
    "OPTIMAL_ENTRY_ANGLE_MIN",
    "OPTIMAL_ENTRY_ANGLE_MAX",
    # Enum
    "CourtStandard",
    "ShotRegion",
    "HoopSide",
    # 데이터 클래스
    "CourtSpec",
    "HoopPosition3D",
    "ShotGeometry",
    "TrajectoryGeometry",
    "RimClearance",
    # 코트 규격
    "get_court_spec",
    "get_three_point_distance",
    # 3D 림/백보드 위치
    "get_hoop_position_2d",
    "get_hoop_position_3d",
    "get_backboard_position_3d",
    # 슛 위치 분석
    "distance_to_hoop",
    "angle_from_hoop",
    "classify_shot_region",
    "is_three_point",
    "is_corner_position",
    "is_in_paint",
    "get_point_value",
    "analyze_shot_location",
    # 슛 궤적 기하학
    "optimal_release_angle",
    "required_velocity",
    "bg_entry_angle",
    "calculate_arc_height",
    "calculate_apex_position",
    "calculate_flight_time",
    "bg_analyze_trajectory",
    # 림 통과 기하학
    "effective_rim_diameter",
    "rim_clearance",
    "minimum_entry_angle",
    "is_bank_shot_viable",
    # 코트 좌표 변환
    "normalize_to_half_court",
    "denormalize_from_half_court",
    "mirror_court_position",
    # 3D 유틸리티
    "is_above_rim",
    "is_in_cylinder",
    # 배치 연산
    "batch_distance_to_hoop",
    "batch_classify_shot_regions",
    "batch_analyze_shot_locations",
    # =========================================================================
    # 카메라 캘리브레이션 유틸리티 (v7.0.0)
    # =========================================================================
    # 상수
    "DEFAULT_RANSAC_THRESHOLD",
    "DEFAULT_RANSAC_CONFIDENCE",
    "DEFAULT_RANSAC_MAX_ITERS",
    "REPROJECTION_ERROR_THRESHOLD",
    "MIN_POINTS_FUNDAMENTAL",
    "MIN_POINTS_ESSENTIAL",
    "MIN_PARALLAX_DEGREES",
    # Enum
    "DistortionModel",
    "FundamentalMethod",
    "TriangulationMethod",
    # 데이터 클래스
    "CameraIntrinsics",
    "DistortionCoeffs",
    "CameraExtrinsics",
    "FundamentalResult",
    "EssentialDecomposition",
    "TriangulationResult",
    "ReprojectionError",
    # 내부 파라미터
    "build_intrinsic_matrix",
    "decompose_intrinsic_matrix",
    "validate_intrinsic_matrix",
    # 왜곡 보정
    "undistort_points",
    "undistort_image",
    "distort_points",
    # 기본 행렬 / 본질 행렬
    "compute_fundamental_matrix",
    "compute_essential_matrix",
    "decompose_essential_matrix",
    # 에피폴라 기하학
    "compute_epipole",
    "compute_epipolar_line",
    "point_to_epipolar_distance",
    # 삼각측량
    "triangulate_points_dlt",
    "triangulate_points_midpoint",
    "triangulate_points",
    # 리프로젝션 오차
    "compute_reprojection_errors",
    "compute_reprojection_stats",
    # 투영 행렬
    "build_projection_matrix",
    "decompose_projection_matrix",
    # 좌표 변환
    "pixel_to_normalized",
    "normalized_to_pixel",
    "world_to_pixel",
    "pixel_to_ray",
    # 배치 연산
    "batch_undistort_points",
    "batch_project_points",
    # 카메라 시야각 / 깊이
    "compute_field_of_view",
    "compute_focal_from_fov",
    "estimate_depth_accuracy",
    # =========================================================================
    # 특징점 매칭 유틸리티 (v7.0.0)
    # =========================================================================
    # 상수
    "DEFAULT_RATIO_THRESHOLD",
    "DEFAULT_CROSS_CHECK",
    "DEFAULT_ORB_FEATURES",
    "DEFAULT_SIFT_FEATURES",
    "DEFAULT_AKAZE_THRESHOLD",
    "DEFAULT_BRISK_THRESHOLD",
    "DEFAULT_HOMOGRAPHY_THRESHOLD",
    "DEFAULT_EPIPOLAR_THRESHOLD",
    "MIN_GOOD_MATCHES",
    # Enum
    "DetectorType",
    "MatcherType",
    "DescriptorNorm",
    # 데이터 클래스
    "KeypointInfo",
    "DetectionResult",
    "MatchPair",
    "MatchResult",
    "MatchQuality",
    # 특징점 검출
    "detect_keypoints",
    "detect_keypoints_multiscale",
    # 디스크립터 매칭
    "match_descriptors",
    "filter_matches_ratio",
    "filter_matches_symmetric",
    # 기하학적 필터링
    "filter_matches_homography",
    "filter_matches_epipolar",
    "filter_matches_distance",
    # 통합 파이프라인
    "match_images",
    # 품질 분석
    "compute_match_quality",
    "compute_descriptor_distance",
    "compute_descriptor_distance_matrix",
    # 유틸리티
    "extract_matched_points",
    "spatial_consistency_filter",
    # =========================================================================
    # 히트맵 유틸리티 (v7.0.0)
    # =========================================================================
    # 상수
    "DEFAULT_PEAK_THRESHOLD",
    "DEFAULT_GAUSSIAN_SIGMA",
    "DEFAULT_NMS_KERNEL_SIZE",
    "COCO_KEYPOINT_NAMES",
    "COCO_SKELETON_CONNECTIONS",
    # Enum
    "SubpixelMethod",
    "HeatmapAggregation",
    # 데이터 클래스
    "HeatmapConfig",
    "HeatmapPeakInfo",
    "SkeletonResult",
    "HeatmapQuality",
    # 피크 검출
    "extract_peaks",
    "extract_peaks_batch",
    "extract_top_peak",
    # 가우시안 히트맵 생성
    "generate_gaussian_heatmap",
    "generate_multi_keypoint_heatmap",
    # 스켈레톤 디코딩
    "decode_heatmaps_to_skeleton",
    "decode_multi_person_heatmaps",
    # 히트맵 앙상블
    "aggregate_heatmaps",
    "flip_heatmap_horizontal",
    # 품질 분석
    "compute_heatmap_quality",
    # 리사이즈/변환
    "resize_heatmap",
    "normalize_heatmap",
]

__version__ = "1.0.0"
__author__ = "SPOIN_COURTVIEW"
