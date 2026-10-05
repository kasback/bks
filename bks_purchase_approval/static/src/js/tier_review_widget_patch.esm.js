/** @odoo-module **/

import {ReviewsTable} from "@base_tier_validation/components/tier_review_widget/tier_review_widget.esm";
import {patch} from "@web/core/utils/patch";

patch(ReviewsTable.prototype, {
    _getReviewData() {
        const fieldName = this.props.name || "review_ids";
        const fieldData = this.props.record.data[fieldName];
        if (!fieldData?.records?.length) {
            return [];
        }
        const rows = fieldData.records.map((record) => record.data);
        rows.sort((left, right) => {
            const leftCancelled = left.status === "cancel";
            const rightCancelled = right.status === "cancel";
            if (leftCancelled !== rightCancelled) {
                return leftCancelled ? -1 : 1;
            }
            const leftSeq = left.sequence || 0;
            const rightSeq = right.sequence || 0;
            if (leftSeq !== rightSeq) {
                return leftSeq - rightSeq;
            }
            return (left.id || 0) - (right.id || 0);
        });
        return rows;
    },
});
