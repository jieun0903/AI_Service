import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def get_availability(equipment_id, quantity, department=None):
    params = {"quantity": quantity}
    if department is not None:
        params["department"] = department
    return client.get(f"/equipment/{equipment_id}/availability", params=params)


@pytest.mark.parametrize(
    "department,equipment_id,quantity,available,expected",
    [
        ("it", 1, 3, 3, True),  # IT 부서는 남은 수량까지 가능
        ("general", 1, 3, 3, False),  # 같은 입력이어도 일반 부서는 0대가 남아 불가
        ("general", 1, 2, 3, True),  # 일반 부서 최대 수량(1대 남음)
        ("it", 1, 4, 3, False),  # 재고 초과는 우선 부서여도 불가
        ("general", 2, 1, 0, False),  # 재고 0
        ("it", 2, 1, 0, False),  # 재고 0이면 우선 부서여도 불가
        (None, 1, 3, 3, True),  # 부서 생략 시 기존 정책 유지
    ],
)
def test_department_policy(department, equipment_id, quantity, available, expected):
    response = get_availability(equipment_id, quantity, department)
    assert response.status_code == 200
    assert response.json() == {
        "equipment_id": equipment_id,
        "requested_quantity": quantity,
        "available_quantity": available,
        "can_allocate": expected,
    }


def test_unsupported_department_is_rejected():
    response = get_availability(1, 1, "sales")
    assert response.status_code == 422


@pytest.mark.parametrize("department,quantity", [("general", 0), ("it", -1)])
def test_invalid_quantity_with_department_is_rejected(department, quantity):
    response = get_availability(1, quantity, department)
    assert response.status_code == 422


def test_unknown_equipment_with_department_returns_404():
    response = get_availability(99, 1, "it")
    assert response.status_code == 404
    assert response.json() == {"detail": "Equipment not found"}


def test_repeated_checks_do_not_change_stock():
    before = client.get("/equipment").json()
    for department in ("it", "general", None):
        for _ in range(3):
            assert get_availability(1, 3, department).status_code == 200
    after = client.get("/equipment").json()
    assert after == before == [
        {"id": 1, "name": "노트북", "available_quantity": 3},
        {"id": 2, "name": "프로젝터", "available_quantity": 0},
    ]
