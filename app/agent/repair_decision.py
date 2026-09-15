import os
import shutil


def decide_repair(
    repository_path,
    source_file,
    backup_file,
    targeted_test_status,
    regression_test_status
):
    """
    Decide whether an applied repair should be accepted
    or rolled back.

    A repair is accepted only when both targeted tests
    and regression tests pass.
    """

    full_path = os.path.join(
        repository_path,
        source_file
    )

    backup_path = os.path.join(
        repository_path,
        backup_file
    )

    print("\n================ REPAIR DECISION ================\n")

    print(
        f"Targeted Tests:   {targeted_test_status}"
    )

    print(
        f"Regression Tests: {regression_test_status}"
    )

    # ------------------------------------------------
    # ACCEPT
    # ------------------------------------------------

    if (
        targeted_test_status == "targeted_test_passed"
        and regression_test_status == "regression_tests_passed"
    ):

        print("\n✓ REPAIR ACCEPTED")
        print("The repair passed targeted and regression tests.")

        # Remove backup because the repair is now accepted.
        if os.path.exists(backup_path):

            os.remove(backup_path)

            print(
                f"Removed backup: {backup_file}"
            )

        print("\n=================================================\n")

        return {
            "decision": "accepted",
            "status": "repair_accepted",
            "rolled_back": False
        }

    # ------------------------------------------------
    # REJECT / ROLLBACK
    # ------------------------------------------------

    print("\n✗ REPAIR REJECTED")
    print("The repair failed validation.")

    if os.path.exists(backup_path):

        try:

            shutil.copy2(
                backup_path,
                full_path
            )

            print(
                f"✓ Rolled back: {source_file}"
            )

            os.remove(backup_path)

            print(
                f"Removed backup: {backup_file}"
            )

            print("\n=================================================\n")

            return {
                "decision": "rejected",
                "status": "repair_rolled_back",
                "rolled_back": True
            }

        except OSError as error:

            print(
                f"Rollback failed: {error}"
            )

            print("\n=================================================\n")

            return {
                "decision": "rejected",
                "status": "rollback_failed",
                "rolled_back": False
            }

    print("⚠ Backup file not found.")
    print("Unable to safely rollback the repair.")

    print("\n=================================================\n")

    return {
        "decision": "rejected",
        "status": "rollback_unavailable",
        "rolled_back": False
    }