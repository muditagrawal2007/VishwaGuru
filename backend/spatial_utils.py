"""
Spatial utilities for geospatial operations and deduplication.
"""
import math
from typing import List, Tuple, Optional
from geopy.distance import geodesic
from sklearn.cluster import DBSCAN
import numpy as np

from backend.models import Issue


def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great circle distance between two points
    on the earth (specified in decimal degrees)

    Returns distance in meters
    """
    return geodesic((lat1, lon1), (lat2, lon2)).meters


def find_nearby_issues(
    issues: List[Issue],
    target_lat: float,
    target_lon: float,
    radius_meters: float = 50.0
) -> List[Tuple[Issue, float]]:
    """
    Find issues within a specified radius of a target location.

    Args:
        issues: List of Issue objects to search through
        target_lat: Target latitude
        target_lon: Target longitude
        radius_meters: Search radius in meters (default 50m)

    Returns:
        List of tuples (issue, distance_meters) for issues within radius
    """
    nearby_issues = []

    for issue in issues:
        if issue.latitude is None or issue.longitude is None:
            continue

        distance = haversine_distance(
            target_lat, target_lon,
            issue.latitude, issue.longitude
        )

        if distance <= radius_meters:
            nearby_issues.append((issue, distance))

    # Sort by distance (closest first)
    nearby_issues.sort(key=lambda x: x[1])

    return nearby_issues


def cluster_issues_dbscan(issues: List[Issue], eps_meters: float = 30.0) -> List[List[Issue]]:
    """
    Cluster issues using DBSCAN algorithm based on spatial proximity.

    Args:
        issues: List of Issue objects with latitude/longitude
        eps_meters: Maximum distance between two samples for one to be considered
                   as in the neighborhood of the other (default 30m)

    Returns:
        List of clusters, where each cluster is a list of Issue objects
    """
    # Filter issues with valid coordinates
    valid_issues = [
        issue for issue in issues
        if issue.latitude is not None and issue.longitude is not None
    ]

    if not valid_issues:
        return []

    # Convert to numpy array for DBSCAN
    coordinates = np.array([
        [issue.latitude, issue.longitude] for issue in valid_issues
    ])

    # Convert eps from meters to degrees (approximate)
    # 1 degree latitude ≈ 111,000 meters
    # 1 degree longitude ≈ 111,000 * cos(latitude) meters
    eps_degrees = eps_meters / 111000  # Rough approximation

    # Perform DBSCAN clustering
    db = DBSCAN(eps=eps_degrees, min_samples=1, metric='haversine').fit(
        np.radians(coordinates)
    )

    # Group issues by cluster
    clusters = {}
    for i, label in enumerate(db.labels_):
        if label not in clusters:
            clusters[label] = []
        clusters[label].append(valid_issues[i])

    # Return clusters as list of lists (exclude noise points labeled as -1)
    return [cluster for label, cluster in clusters.items() if label != -1]


def get_cluster_representative(cluster: List[Issue]) -> Issue:
    """
    Get the representative issue from a cluster.
    Uses the issue with the most upvotes, or the oldest if tie.

    Args:
        cluster: List of issues in the same cluster

    Returns:
        Representative issue from the cluster
    """
    if not cluster:
        raise ValueError("Cluster cannot be empty")

    # Sort by upvotes (descending), then by creation date (ascending)
    sorted_issues = sorted(
        cluster,
        key=lambda x: (-(x.upvotes or 0), x.created_at)
    )

    return sorted_issues[0]


def calculate_cluster_centroid(cluster: List[Issue]) -> Tuple[float, float]:
    """
    Calculate the centroid (average position) of a cluster of issues.

    Args:
        cluster: List of issues with coordinates

    Returns:
        Tuple of (latitude, longitude) representing the centroid
    """
    valid_issues = [
        issue for issue in cluster
        if issue.latitude is not None and issue.longitude is not None
    ]

    if not valid_issues:
        raise ValueError("No valid coordinates in cluster")

    avg_lat = sum(issue.latitude for issue in valid_issues) / len(valid_issues)
    avg_lon = sum(issue.longitude for issue in valid_issues) / len(valid_issues)

    return avg_lat, avg_lon