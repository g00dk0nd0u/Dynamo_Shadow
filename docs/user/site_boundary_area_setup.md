# Site Boundary Area / 敷地境界エリア

## Recommended setup / 推奨作成手順

1. Create an Area Scheme / Area Schemeを作成: `Shadow Analysis / 日影検討`.
2. Create an Area Plan at the site level / 敷地レベルにArea Planを作成します。
3. Draw the site boundary with Area Boundary lines / Area Boundaryで敷地境界を描きます。
4. Place exactly one Area inside the closed boundary / 閉じた領域内にAreaを1個配置します。
5. In Dynamo Player, select the placed Area body once / Dynamo PlayerでArea本体を1回選択します。

Recommended Area name / 推奨Area名: `Site Boundary / 敷地境界`.

## Initial limitations / 初期版の制約

- One Area only / Area 1個
- One outer loop only / 外周1個
- No holes or islands / 孔・飛び地なし
- Straight Area Boundary segments only / 直線境界のみ
- Placed and closed Area in the host model / ホストモデル内の配置済み閉鎖Area

## Do not select / 選択してはいけないもの

- Area Boundary lines / エリア境界線
- Area Tag / エリアタグ
- Model Line / モデル線
- Detail Line / 詳細線
- Filled Region / 塗り潰し領域
- Property Line / 敷地境界線
- Floor / 床
- Generic Model family / 一般モデルファミリー

## Dynamo Player selection / 選択方法

`Site Boundary Area / 敷地境界エリア` → `Select` → click inside the Area body.

Select the Area body, not the Area Tag. / Area TagではなくArea本体を選択してください。

## Result / 結果

- Valid Area: Dynamo_Shadow generates 5m/10m distance masks.
- Invalid Area: shadow duration and equal-time contour calculations continue; only boundary-dependent masks are unavailable.

## Notes / 注意

This stage does not certify legal OK/NG, does not automatically determine the ordinance classification, and is not permit certification.

## Dynamo Player optional-input note / Dynamo Player任意入力の注意

`Site Boundary Area / 敷地境界エリア` is saved as a Dynamo Player `hostSelection` input. The Python pipeline still treats `site_boundary` as optional when `None` is supplied through tests or API-style execution, so core shadow duration and equal-time contours can continue without boundary masks.

Dynamo Player behavior with an unselected `hostSelection` must be confirmed in Revit 2024.3 / Dynamo 3.3. If Player disables Run while the Area is unselected, this PR adopts the current UI behavior that the Area selection is required in Dynamo Player, while preserving optional `None` handling in Python. No dummy ElementId, dummy element, or fixed GUID is used.

## Selected shadow limit comparison

When a valid placed Area is selected and measurement masks are generated, Dynamo_Shadow can also compare the near (5 m to 10 m) and far (over 10 m) maximum shadow durations with a specific regulatory shadow limit preset selected in Dynamo Player.

This comparison is only a numerical check against the user-selected preset. It is not a legal compliance judgement, ordinance applicability certification, or permit-ready result. The `standard_all` and `hokkaido_all` presets display candidate contour levels and do not produce a unique near/far comparison.
