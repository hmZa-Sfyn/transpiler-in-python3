// main.xc
// Small example program in the hypothetical language

include <stdio>
include <string>

def:BUFFER      = 2048;
def:MAX_PLAYERS = 8;
def:FLAG        = "DEV";

struct:Player = {
    int:id;
    int:points;
    char[50]:name;
    bool:is_active;
};

int:score_multiplier = 100;

fn:print_player = (struct:Player *p) => {
    printf("Player #%d  %-20s  %6d pts   %s\n",
        p->id,
        p->name,
        p->points,
        p->is_active ? "ACTIVE" : "inactive");
};

fn:update_points = (struct:Player *p | int:delta) => {
    p->points += delta * score_multiplier;

    if:(p->points < 0) => {
        p->points = 0;
    }
};

int:main = (int:argc | char*:argv[]) => {
    printf("\n=== %s BUILD ===\n\n", FLAG);

    struct:Player players[MAX_PLAYERS];

    // Initialize all players
    for:loop = (int:i = 0 | i < MAX_PLAYERS | i++) => {
        players[i].id        = i + 1;
        players[i].points    = 0;
        players[i].is_active = (i < 5);

        strcpy(players[i].name, "Player_");
        char tmp[8];
        sprintf(tmp, "%d", i + 1);
        strcat(players[i].name, tmp);
    }

    // Give names to the first few
    strcpy(players[0].name, "Alice");
    strcpy(players[1].name, "Bob");
    strcpy(players[2].name, "Charlie");
    strcpy(players[3].name, "Dana");

    // Show initial state
    printf("Initial roster:\n");
    for:each = (players | struct:Player *p | int:i) => {
        if:(i >= MAX_PLAYERS) break;
        print_player(&players[i]);
    }

    printf("\n--- Round 1 ---\n");

    // Award / deduct points
    update_points(&players[0],  42);
    update_points(&players[1],  19);
    update_points(&players[2], -15);
    update_points(&players[3],  60);
    update_points(&players[7],   5);   // inactive player still gets points

    // Show results with match example
    for:loop = (int:i = 0 | i < 5 | i++) => {
        int:pts = players[i].points;

        match:(pts) => {
            0   => printf("  %s → still at zero\n", players[i].name);
            4200 => printf("  %s → JACKPOT! 4200 points!\n", players[i].name);
            _ if:(pts >= 3000) => printf("  %s → outstanding! (%d pts)\n", players[i].name, pts);
            _   => printf("  %s → %d points\n", players[i].name, pts);
        }
    }

    // Show command-line arguments if any
    if:(argc > 1) => {
        printf("\nCommand-line arguments received:\n");
        for:each = (argv | char**:arg | int:idx) => {
            if:(idx == 0) continue;
            printf("  arg[%d] = %s\n", idx, *arg);
        }
    }

    // Final scoreboard
    printf("\nFinal scoreboard:\n");
    for:each = (players | struct:Player *p) => {
        print_player(p);
    }

    printf("\nGame over.\n");
    return 0;
}