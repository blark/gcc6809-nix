// EXPECT: 0
// gcc6809 ICE: signed byte multiplication inside a loop with live registers.
// Reduced from anachron8-sw tetris/tetris.c:try_rotate; the original
// compiler before signed-multiply correction compiles it, while the current
// compiler reports "unable to find a register to spill in class A_REGS".
typedef signed char int8_t;
typedef unsigned char uint8_t;
extern uint8_t current_rot, current_piece;
extern int8_t piece_x, piece_y;
extern const int8_t kicks_i[4][5][2], kicks_jlstz[4][5][2];
extern uint8_t check_collision(int x, int y, int rot);
extern void piece_moved(void);
uint8_t try_rotate(int8_t dir)
{
    uint8_t new_rot = (current_rot + dir) & 3;
    const int8_t (*k)[2];
    int8_t dx = 0, dy = 0;
    uint8_t i;
    if (dir > 0)
        k = (current_piece == 0 ? kicks_i : kicks_jlstz)[current_rot];
    else
        k = (current_piece == 0 ? kicks_i : kicks_jlstz)[new_rot];
    for (i = 0; ; i++) {
        if (!check_collision(piece_x + dx, piece_y + dy, new_rot)) {
            piece_x += dx;
            piece_y += dy;
            current_rot = new_rot;
            piece_moved();
            return 1;
        }
        if (i == 4) return 0;
        dx = k[i][0] * dir;
        dy = k[i][1] * dir;
    }
}
uint8_t current_rot, current_piece;
int8_t piece_x, piece_y;
const int8_t kicks_i[4][5][2] = { {{1, 2}} };
const int8_t kicks_jlstz[4][5][2] = { { {0, 0} }, { {0, 0} },
                                     { {0, 0} }, { {-1, 2} } };
static uint8_t collision_calls, moved_calls;
uint8_t check_collision(int x, int y, int rot)
{
    (void)x; (void)y; (void)rot;
    return ++collision_calls == 1;
}
void piece_moved(void) { ++moved_calls; }
int main(void)
{
    piece_x = 4;
    piece_y = 4;
    if (!try_rotate(1) || piece_x != 5 || piece_y != 6 ||
        current_rot != 1 || collision_calls != 2 || moved_calls != 1)
        return 1;
    piece_x = 4;
    piece_y = 4;
    current_rot = 0;
    collision_calls = 0;
    if (!try_rotate(-1) || piece_x != 5 || piece_y != 2 ||
        current_rot != 3 || collision_calls != 2 || moved_calls != 2)
        return 2;
    return 0;
}
