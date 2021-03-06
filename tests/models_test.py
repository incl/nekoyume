import datetime

from coincurve import PrivateKey, PublicKey
from pytest import fixture, raises

from nekoyume.exc import InvalidMoveError
from nekoyume.models import (Block,
                             CreateNovice,
                             HackAndSlash,
                             LevelUp,
                             Move,
                             Node,
                             Say,
                             Sleep,
                             User,
                             get_address)


@fixture
def fx_user2(fx_session):
    user = User(PrivateKey())
    user.session = fx_session
    return user


@fixture
def fx_other_user(fx_other_session):
    user = User(PrivateKey())
    user.session = fx_other_session
    return user


def test_move_confirmed_and_validation(fx_user, fx_novice_status):
    move = Move()
    assert not move.confirmed
    assert not move.valid

    move = fx_user.create_novice(fx_novice_status)

    assert not move.confirmed
    assert move.valid

    block = Block.create(fx_user, [move])

    assert move.block_id
    assert move.confirmed
    assert move.valid

    move.tax = 1
    assert not move.valid
    assert not block.valid


def test_level_up(fx_user, fx_novice_status):
    move = fx_user.create_novice(fx_novice_status)
    Block.create(fx_user, [move])

    while True:
        if fx_user.avatar().exp >= 8:
            break
        move = fx_user.hack_and_slash()
        Block.create(fx_user, [move])

        if fx_user.avatar().hp <= 0:
            move = fx_user.sleep()
            Block.create(fx_user, [move])

    assert fx_user.avatar().level >= 2


def test_block_validation(fx_user, fx_novice_status):
    move = fx_user.create_novice(fx_novice_status)
    block = Block.create(fx_user, [move])
    assert block.valid
    move.id = ('00000000000000000000000000000000'
               '00000000000000000000000000000000')
    assert not block.valid


def test_avatar_basic_moves(fx_user, fx_novice_status):
    moves = [
        CreateNovice(details=fx_novice_status),
        HackAndSlash(),
        Sleep(),
        Say(details={'content': 'hi'}),
        LevelUp(details={'new_status': 'strength'}),
    ]
    for move in moves:
        move = fx_user.move(move)
        block = Block.create(fx_user, [move])
        assert move.valid
        assert move.confirmed
        assert block.valid
        assert fx_user.avatar(block.id)


def test_block_broadcast(fx_user, fx_session, fx_other_user, fx_other_session,
                         fx_server):
    assert fx_other_session.query(Block).count() == 0
    assert fx_session.query(Block).count() == 0

    fx_other_session.add(Node(url=fx_server.url,
                              last_connected_at=datetime.datetime.utcnow()))
    fx_other_session.commit()

    block = Block.create(fx_other_user, [])
    block.broadcast(session=fx_other_session)
    assert fx_other_session.query(Block).count() == 1
    assert fx_session.query(Block).count() == 1


def test_move_broadcast(fx_user, fx_session, fx_other_user, fx_other_session,
                        fx_server, fx_novice_status):
    assert fx_other_session.query(Move).count() == 0
    assert fx_session.query(Move).count() == 0

    fx_other_session.add(Node(url=fx_server.url,
                              last_connected_at=datetime.datetime.utcnow()))
    fx_other_session.commit()

    move = fx_other_user.create_novice(fx_novice_status)
    assert not fx_session.query(Move).get(move.id)

    move.broadcast(session=fx_other_session)
    assert fx_session.query(Move).get(move.id)


def test_node(fx_server, fx_session):
    assert fx_server.url
    assert Node.get(fx_server.url, session=fx_session)
    assert Node.get(fx_server.url, session=fx_session).url == fx_server.url
    assert Node.get(fx_server.url, session=fx_session).last_connected_at


def test_sync(fx_user, fx_session, fx_other_user, fx_other_session, fx_server,
              fx_novice_status):
    assert fx_other_session.query(Block).count() == 0
    assert fx_session.query(Block).count() == 0

    Block.sync(Node(url=fx_server.url), fx_other_session)
    assert fx_other_session.query(Block).count() == 0
    assert fx_session.query(Block).count() == 0

    Block.create(fx_other_user, [])
    Block.sync(Node(url=fx_server.url), fx_other_session)
    assert fx_other_session.query(Block).count() == 1
    assert fx_session.query(Block).count() == 0

    move = fx_user.create_novice(fx_novice_status)
    Block.create(fx_user, [move])
    Block.create(fx_user, [])
    Block.create(fx_user, [])

    assert fx_other_session.query(Block).count() == 1
    assert fx_other_session.query(Move).count() == 0
    assert fx_session.query(Block).count() == 3
    assert fx_session.query(Move).count() == 1

    Block.sync(Node(url=fx_server.url), fx_other_session)
    assert fx_other_session.query(Block).count() == 3
    assert fx_other_session.query(Move).count() == 1
    assert fx_session.query(Block).count() == 3
    assert fx_session.query(Move).count() == 1


def test_flush_session_while_syncing(fx_user, fx_session, fx_other_session,
                                     fx_novice_status):
    # 1. block validation failure scenario
    # syncing without flushing can cause block validation failure
    move = fx_user.create_novice(fx_novice_status)
    invalid_block = Block.create(fx_user, [move])
    fx_session.delete(invalid_block)

    # syncing valid blocks from another node
    new_blocks = [
        {
            "created_at": "2018-04-13 11:36:17.920869",
            "creator": "ET8ngv45qwhkDiJS1ZrUxndcGTzHxjPZDs",
            "difficulty": 0,
            "hash": "da0182c494660af0d9dd288839ceb86498708f38c800363cd46ed1730013a4d8", # noqa
            "id": 1,
            "version": 2,
            "moves": [],
            "prev_hash": None,
            "root_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", # noqa
            "suffix": "00"
        },
        {
            "created_at": "2018-04-13 11:36:17.935392",
            "creator": "ET8ngv45qwhkDiJS1ZrUxndcGTzHxjPZDs",
            "difficulty": 1,
            "hash": "014c44b9382a45c2a70d817c090e6b78af22b8f34b57fd7edb474344f25c439c", # noqa
            "id": 2,
            "version": 2,
            "moves": [],
            "prev_hash": "da0182c494660af0d9dd288839ceb86498708f38c800363cd46ed1730013a4d8", # noqa
            "root_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855", # noqa
            "suffix": "0b"
        }
    ]

    def add_block(new_block):
        block = Block.deserialize(new_block)
        fx_session.add(block)
        return block

    valid_block1 = add_block(new_blocks[0])
    valid_block2 = add_block(new_blocks[1])

    assert invalid_block.hash == \
        fx_session.query(Block).get(valid_block2.id - 1).hash
    assert valid_block2.valid is False

    fx_session.query(Block).delete()

    # 2. valid scenario
    # flush session after deleting the invalid block
    move = fx_user.create_novice(fx_novice_status)
    invalid_block = Block.create(fx_user, [move])
    fx_session.delete(invalid_block)
    fx_session.flush()

    valid_block1 = add_block(new_blocks[0])
    valid_block2 = add_block(new_blocks[1])

    assert valid_block1.hash == \
        fx_session.query(Block).get(valid_block2.id - 1).hash
    assert valid_block2.valid


def test_get_address():
    raw_key = bytes.fromhex(
        '04fb0af727d1839557ea5214a7b7dd799c05dab9da63329a6c6d9836fd19a29ce'
        'bc34f7ba31877b22f6767bb1d9f376a33fc0f28f37ada368611b011c01dbef90f'
    )
    pubkey = PublicKey(raw_key)
    assert '0x80e0b0a7cc8001086a37648f993b2bd855d0ab59' == get_address(pubkey)


def test_hack_and_slash_execute(fx_user, fx_novice_status):
    move = fx_user.create_novice(fx_novice_status)
    Block.create(fx_user, [move])
    avatar = fx_user.avatar()
    avatar.hp = 0
    move = fx_user.move(HackAndSlash())
    Block.create(fx_user, [move])
    with raises(InvalidMoveError):
        move.execute(avatar)
