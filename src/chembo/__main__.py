import multiprocessing
import sys
import typing_extensions  # Initialize the Python 3.10 Self backport before Qt.


def main():
    multiprocessing.freeze_support()
    if len(sys.argv) > 1 and sys.argv[1] == "--worker":
        from chembo.worker import main as worker_main
        return worker_main(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == "--verify-ui":
        from chembo.verification import main as verify_main
        return verify_main(sys.argv[2:])
    from chembo.app import main as app_main
    return app_main()


if __name__ == "__main__":
    sys.exit(main())
